"""
KMRL NexusAI — Reinforcement Learning Module
=============================================
Learns from historical induction decisions and operational outcomes
to continuously improve the optimization engine's soft-constraint weights.

Algorithm: Proximal Policy Optimization (PPO) via custom lightweight
           tabular Q-learning for the weight adaptation problem.

State:     fleet composition snapshot (health, mileage, certs, time)
Action:    adjust soft-constraint weight vector (δ per dimension)
Reward:    operational outcome signal (no withdrawal=+1, withdrawal=-2,
           mileage balanced=+0.5, SLA met=+0.3)
"""
from __future__ import annotations

import json
import logging
import math
import os
import pickle
import random
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

MODEL_DIR = Path(os.getenv("ML_MODEL_PATH", "/app/models"))


# ── State / Action / Reward ───────────────────────────────────────────────

@dataclass
class FleetState:
    """Compact state representation for RL agent."""
    avg_brake_health: float       # 0–100
    avg_hvac_health: float
    avg_door_health: float
    fleet_avg_mileage_km: float
    mileage_std_dev: float
    cert_expiry_within_7d: int    # count
    critical_jobs_open: int
    branding_deficit_count: int   # trains below SLA
    standby_ratio: float          # standby/total
    time_of_day_bucket: int       # 0=day 1=evening 2=night

    def to_vector(self) -> np.ndarray:
        return np.array([
            self.avg_brake_health / 100,
            self.avg_hvac_health / 100,
            self.avg_door_health / 100,
            min(self.fleet_avg_mileage_km / 300_000, 1.0),
            min(self.mileage_std_dev / 50_000, 1.0),
            min(self.cert_expiry_within_7d / 5, 1.0),
            min(self.critical_jobs_open / 5, 1.0),
            min(self.branding_deficit_count / 5, 1.0),
            self.standby_ratio,
            self.time_of_day_bucket / 2.0,
        ], dtype=np.float32)


@dataclass
class WeightVector:
    """Soft-constraint weights used by the optimizer."""
    mileage_balance: float = 25.0
    branding_sla: float = 20.0
    cleaning_ready: float = 15.0
    system_health: float = 20.0
    ibl_recency: float = 10.0
    ml_risk_inverse: float = 10.0

    def to_array(self) -> np.ndarray:
        return np.array([
            self.mileage_balance, self.branding_sla, self.cleaning_ready,
            self.system_health, self.ibl_recency, self.ml_risk_inverse,
        ], dtype=np.float32)

    @classmethod
    def from_array(cls, arr: np.ndarray) -> "WeightVector":
        return cls(*arr.tolist())

    def normalize(self) -> "WeightVector":
        """Ensure weights sum to 100 and are all positive."""
        arr = np.clip(self.to_array(), 1.0, 50.0)
        arr = arr / arr.sum() * 100.0
        return WeightVector.from_array(arr)

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass
class Transition:
    """Single SARS transition for experience replay."""
    state: np.ndarray
    action: np.ndarray           # δ applied to weight vector
    reward: float
    next_state: np.ndarray
    done: bool
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    outcome: str = ""            # human-readable outcome label


@dataclass
class OperationalOutcome:
    """Post-hoc outcome recorded after a service day."""
    plan_date: date
    planned_revenue: int
    actual_revenue: int
    withdrawals: int             # unplanned service withdrawals
    delays: int
    mileage_variance_km: float
    sla_compliance_pct: float
    supervisor_overrides: int    # human overrides of AI plan
    notes: str = ""

    def compute_reward(self) -> float:
        """
        Reward signal for the RL agent.
        Range: approximately -5 to +3.
        """
        reward = 0.0

        # Revenue attainment (main signal)
        attainment = self.actual_revenue / max(self.planned_revenue, 1)
        reward += 2.0 * (attainment - 0.9)   # +1 at 100%, 0 at 90%, -1.8 at 0%

        # Withdrawal penalty
        reward -= self.withdrawals * 0.8

        # Delay penalty
        reward -= self.delays * 0.3

        # Mileage balance bonus
        if self.mileage_variance_km < 20:
            reward += 0.5
        elif self.mileage_variance_km > 50:
            reward -= 0.3

        # SLA compliance bonus
        reward += (self.sla_compliance_pct - 90) / 100

        # Override penalty (AI was wrong)
        reward -= self.supervisor_overrides * 0.2

        return round(float(np.clip(reward, -5.0, 3.0)), 3)


# ── Replay Buffer ─────────────────────────────────────────────────────────

class ReplayBuffer:
    """Circular experience replay buffer."""

    def __init__(self, capacity: int = 10_000):
        self.buffer: deque[Transition] = deque(maxlen=capacity)

    def push(self, transition: Transition) -> None:
        self.buffer.append(transition)

    def sample(self, batch_size: int) -> list[Transition]:
        return random.sample(self.buffer, min(batch_size, len(self.buffer)))

    def __len__(self) -> int:
        return len(self.buffer)

    def save(self, path: Path) -> None:
        with open(path, "wb") as f:
            pickle.dump(list(self.buffer), f)

    def load(self, path: Path) -> None:
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.buffer = deque(data, maxlen=self.buffer.maxlen)


# ── RL Agent (Deep Q-Network style weight adapter) ────────────────────────

class WeightAdaptationAgent:
    """
    Lightweight RL agent that adapts soft-constraint weights based on
    operational outcomes.

    Architecture: 2-layer MLP approximating Q(state, action) where
    action = discrete perturbation index (which weight to increase/decrease).

    Actions:
      0–5: increase weight i by δ
      6–11: decrease weight i by δ
      12: no change (exploit current weights)
    """

    N_WEIGHTS = 6
    N_ACTIONS = N_WEIGHTS * 2 + 1   # 13
    DELTA = 2.0                      # weight perturbation magnitude
    GAMMA = 0.95                     # discount factor
    LR = 1e-3
    EPSILON_START = 1.0
    EPSILON_END = 0.05
    EPSILON_DECAY = 0.995
    BATCH_SIZE = 64
    TARGET_UPDATE_FREQ = 50          # steps before target net sync
    VERSION = "1.0.0"

    def __init__(self):
        self.weights = WeightVector()
        self.replay_buffer = ReplayBuffer(capacity=5_000)
        self.epsilon = self.EPSILON_START
        self.step_count = 0
        self.episode_count = 0

        # Simple neural network: input=10, hidden=32, output=13
        self._init_networks()

        self._is_trained = False

    def _init_networks(self) -> None:
        """Initialize Q-network and target network with Xavier init."""
        np.random.seed(0)
        self.q_net = self._make_network()
        self.target_net = self._make_network()
        self._sync_target()

    def _make_network(self) -> dict[str, np.ndarray]:
        """Xavier-initialized 2-layer MLP weights."""
        fan_in_1, fan_out_1 = 10, 32
        fan_in_2, fan_out_2 = 32, self.N_ACTIONS
        return {
            "W1": np.random.randn(fan_in_1, fan_out_1) * math.sqrt(2 / fan_in_1),
            "b1": np.zeros(fan_out_1),
            "W2": np.random.randn(fan_in_2, fan_out_2) * math.sqrt(2 / fan_in_2),
            "b2": np.zeros(fan_out_2),
        }

    def _forward(self, net: dict, x: np.ndarray) -> np.ndarray:
        h = np.tanh(x @ net["W1"] + net["b1"])
        return h @ net["W2"] + net["b2"]

    def _sync_target(self) -> None:
        self.target_net = {k: v.copy() for k, v in self.q_net.items()}

    def select_action(self, state: FleetState) -> int:
        """Epsilon-greedy action selection."""
        if random.random() < self.epsilon:
            return random.randint(0, self.N_ACTIONS - 1)
        q_values = self._forward(self.q_net, state.to_vector())
        return int(np.argmax(q_values))

    def apply_action(self, action: int) -> WeightVector:
        """Apply selected action to current weight vector."""
        weights_arr = self.weights.to_array().copy()
        if action < self.N_WEIGHTS:
            weights_arr[action] += self.DELTA
        elif action < self.N_WEIGHTS * 2:
            weights_arr[action - self.N_WEIGHTS] -= self.DELTA
        # action == 12: no change
        new_weights = WeightVector.from_array(weights_arr).normalize()
        self.weights = new_weights
        return new_weights

    def record_transition(
        self,
        state: FleetState,
        action: int,
        outcome: OperationalOutcome,
        next_state: FleetState,
        done: bool = False,
    ) -> float:
        """Store transition and trigger learning if buffer has enough samples."""
        reward = outcome.compute_reward()
        transition = Transition(
            state=state.to_vector(),
            action=np.array([action]),
            reward=reward,
            next_state=next_state.to_vector(),
            done=done,
            outcome=outcome.notes or f"reward={reward:.2f}",
        )
        self.replay_buffer.push(transition)
        self.step_count += 1
        self.epsilon = max(self.EPSILON_END, self.epsilon * self.EPSILON_DECAY)

        if len(self.replay_buffer) >= self.BATCH_SIZE:
            loss = self._learn()
            if self.step_count % self.TARGET_UPDATE_FREQ == 0:
                self._sync_target()
            return loss
        return 0.0

    def _learn(self) -> float:
        """One gradient step of DQN update (numpy-only implementation)."""
        batch = self.replay_buffer.sample(self.BATCH_SIZE)

        states = np.stack([t.state for t in batch])
        actions = np.array([t.action[0] for t in batch], dtype=int)
        rewards = np.array([t.reward for t in batch])
        next_states = np.stack([t.next_state for t in batch])
        dones = np.array([t.done for t in batch], dtype=float)

        # Current Q values
        q_current = self._forward(self.q_net, states)
        q_selected = q_current[np.arange(self.BATCH_SIZE), actions]

        # Target Q values (Bellman)
        q_next = self._forward(self.target_net, next_states).max(axis=1)
        q_target = rewards + self.GAMMA * q_next * (1 - dones)

        # TD error
        td_error = q_target - q_selected
        loss = float(np.mean(td_error ** 2))

        # Gradient step (manual backprop for 2-layer MLP)
        # dL/dW2
        h1 = np.tanh(states @ self.q_net["W1"] + self.q_net["b1"])
        delta_out = np.zeros_like(q_current)
        delta_out[np.arange(self.BATCH_SIZE), actions] = -2 * td_error / self.BATCH_SIZE

        dW2 = h1.T @ delta_out
        db2 = delta_out.sum(axis=0)

        # dL/dW1
        delta_h1 = (delta_out @ self.q_net["W2"].T) * (1 - h1 ** 2)
        dW1 = states.T @ delta_h1
        db1 = delta_h1.sum(axis=0)

        # Update weights
        self.q_net["W2"] -= self.LR * dW2
        self.q_net["b2"] -= self.LR * db2
        self.q_net["W1"] -= self.LR * dW1
        self.q_net["b1"] -= self.LR * db1

        self._is_trained = True
        return loss

    def get_current_weights(self) -> WeightVector:
        return self.weights

    def get_weight_history(self) -> list[dict]:
        """Return recent weight evolution for visualization."""
        # In production: persist to DB; here we return current snapshot
        return [self.weights.to_dict()]

    def save(self, path: Path | None = None) -> None:
        path = path or MODEL_DIR / f"rl_agent_v{self.VERSION}"
        path.mkdir(parents=True, exist_ok=True)
        np.save(path / "q_net_W1.npy", self.q_net["W1"])
        np.save(path / "q_net_b1.npy", self.q_net["b1"])
        np.save(path / "q_net_W2.npy", self.q_net["W2"])
        np.save(path / "q_net_b2.npy", self.q_net["b2"])
        self.replay_buffer.save(path / "replay_buffer.pkl")
        meta = {
            "version": self.VERSION,
            "step_count": self.step_count,
            "episode_count": self.episode_count,
            "epsilon": self.epsilon,
            "current_weights": self.weights.to_dict(),
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        (path / "metadata.json").write_text(json.dumps(meta, indent=2))
        logger.info("RL agent saved: steps=%d epsilon=%.3f", self.step_count, self.epsilon)

    @classmethod
    def load(cls, path: Path) -> "WeightAdaptationAgent":
        meta = json.loads((path / "metadata.json").read_text())
        agent = cls()
        agent.q_net["W1"] = np.load(path / "q_net_W1.npy")
        agent.q_net["b1"] = np.load(path / "q_net_b1.npy")
        agent.q_net["W2"] = np.load(path / "q_net_W2.npy")
        agent.q_net["b2"] = np.load(path / "q_net_b2.npy")
        agent._sync_target()
        if (path / "replay_buffer.pkl").exists():
            agent.replay_buffer.load(path / "replay_buffer.pkl")
        agent.step_count = meta.get("step_count", 0)
        agent.epsilon = meta.get("epsilon", cls.EPSILON_END)
        agent.weights = WeightVector(**meta.get("current_weights", {}))
        agent._is_trained = True
        logger.info("RL agent loaded: steps=%d epsilon=%.3f", agent.step_count, agent.epsilon)
        return agent


# ── Historical Learning Service ───────────────────────────────────────────

class HistoricalLearningService:
    """
    Orchestrates the full RL feedback loop:
    1. After each service day, record outcome
    2. Convert to reward signal
    3. Feed to RL agent
    4. Updated weights exported to optimizer
    """

    def __init__(self):
        self.agent = self._load_or_create_agent()
        self._outcomes_processed = 0

    def _load_or_create_agent(self) -> WeightAdaptationAgent:
        agent_path = MODEL_DIR / f"rl_agent_v{WeightAdaptationAgent.VERSION}"
        if agent_path.exists():
            try:
                return WeightAdaptationAgent.load(agent_path)
            except Exception as e:
                logger.warning("Failed to load RL agent, creating new: %s", e)
        return WeightAdaptationAgent()

    def process_outcome(
        self,
        pre_plan_state: FleetState,
        action_taken: int,
        outcome: OperationalOutcome,
        post_plan_state: FleetState,
    ) -> dict[str, Any]:
        """
        Record operational outcome and update agent.
        Called by Celery worker after each service day.
        """
        reward = outcome.compute_reward()
        loss = self.agent.record_transition(
            pre_plan_state, action_taken, outcome, post_plan_state
        )
        self._outcomes_processed += 1

        # Persist agent periodically
        if self._outcomes_processed % 10 == 0:
            self.agent.save()

        updated_weights = self.agent.get_current_weights()
        logger.info(
            "RL update: date=%s reward=%.2f loss=%.4f epsilon=%.3f weights=%s",
            outcome.plan_date, reward, loss, self.agent.epsilon,
            {k: round(v, 1) for k, v in updated_weights.to_dict().items()}
        )

        return {
            "reward": reward,
            "loss": loss,
            "epsilon": round(self.agent.epsilon, 3),
            "step_count": self.agent.step_count,
            "updated_weights": updated_weights.to_dict(),
            "outcome_summary": {
                "plan_date": str(outcome.plan_date),
                "revenue_attainment": f"{outcome.actual_revenue}/{outcome.planned_revenue}",
                "withdrawals": outcome.withdrawals,
                "sla_pct": outcome.sla_compliance_pct,
            },
        }

    def get_optimized_weights(self) -> WeightVector:
        """Return current RL-optimized weights for use in optimizer."""
        return self.agent.get_current_weights()

    def simulate_learning(self, n_episodes: int = 100) -> dict[str, Any]:
        """
        Simulate learning from synthetic historical data.
        Used for warm-starting before real data is available.
        """
        logger.info("Simulating RL learning: %d episodes", n_episodes)
        np.random.seed(42)
        rewards_history = []

        for ep in range(n_episodes):
            state = FleetState(
                avg_brake_health=np.random.uniform(70, 100),
                avg_hvac_health=np.random.uniform(75, 100),
                avg_door_health=np.random.uniform(80, 100),
                fleet_avg_mileage_km=np.random.uniform(150_000, 300_000),
                mileage_std_dev=np.random.uniform(5_000, 40_000),
                cert_expiry_within_7d=np.random.randint(0, 4),
                critical_jobs_open=np.random.randint(0, 3),
                branding_deficit_count=np.random.randint(0, 3),
                standby_ratio=np.random.uniform(0.08, 0.2),
                time_of_day_bucket=2,
            )
            action = self.agent.select_action(state)
            self.agent.apply_action(action)

            outcome = OperationalOutcome(
                plan_date=date.today(),
                planned_revenue=18,
                actual_revenue=np.random.randint(15, 20),
                withdrawals=np.random.randint(0, 3),
                delays=np.random.randint(0, 5),
                mileage_variance_km=np.random.uniform(5, 60),
                sla_compliance_pct=np.random.uniform(80, 100),
                supervisor_overrides=np.random.randint(0, 3),
            )
            reward = outcome.compute_reward()
            rewards_history.append(reward)

            next_state = FleetState(
                avg_brake_health=state.avg_brake_health - np.random.uniform(0, 1),
                avg_hvac_health=state.avg_hvac_health,
                avg_door_health=state.avg_door_health,
                fleet_avg_mileage_km=state.fleet_avg_mileage_km + 150,
                mileage_std_dev=state.mileage_std_dev,
                cert_expiry_within_7d=state.cert_expiry_within_7d,
                critical_jobs_open=state.critical_jobs_open,
                branding_deficit_count=state.branding_deficit_count,
                standby_ratio=state.standby_ratio,
                time_of_day_bucket=2,
            )
            self.agent.record_transition(state, action, outcome, next_state)

        self.agent.episode_count += n_episodes
        self.agent.save()

        avg_reward = float(np.mean(rewards_history))
        return {
            "episodes": n_episodes,
            "avg_reward": round(avg_reward, 3),
            "final_epsilon": round(self.agent.epsilon, 3),
            "final_weights": self.agent.get_current_weights().to_dict(),
            "reward_trend": [round(float(r), 2) for r in rewards_history[-20:]],
        }
