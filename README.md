🚆 AI-Driven Train Induction Planning & Scheduling for KMRL

Transforming Kochi Metro operations with intelligent scheduling and predictive fleet management.

📖 Overview

Kochi Metro Rail Limited (KMRL) operates a growing fleet of 25+ trainsets, and by 2027, this is expected to expand to 40 trainsets across two depots. Every night, operations teams face a high-stakes decision:

Which trains enter service at dawn

Which remain on standby

Which are held back for maintenance

Currently, this process relies on siloed spreadsheets, manual logs, and WhatsApp updates—making it opaque, error-prone, and non-scalable.

This project introduces an AI-driven, data-powered platform to automate and optimize train induction planning, ensuring higher fleet availability, lower lifecycle costs, and superior operational efficiency.

🎯 Key Challenges

Fitness Certificates – Ensuring valid approvals from Rolling Stock, Signalling, and Telecom departments.

Job-Card Status – Managing open vs. closed work orders from IBM Maximo.

Branding Priorities – Meeting contractual commitments for exterior wrap exposure.

Mileage Balancing – Optimizing kilometer allocation to reduce wear on bogies, brake pads, and HVAC systems.

Cleaning & Detailing Slots – Allocating manpower and bays for interior deep-cleaning.

Stabling Geometry – Minimizing shunting and morning turn-out time by strategic bay positioning.

Pain Points of the Current Manual Process:

Missed clearances → unscheduled rake withdrawals → punctuality drop

Uneven mileage → accelerated component fatigue → higher maintenance costs

Poor visibility of branding priorities → SLA breaches → revenue penalties

Excessive night-time shunting → increased energy consumption & track risks

💡 Solution Features

This AI-driven platform offers:

Multi-source Data Integration: Maximo exports, IoT sensors, UNS streams, and manual overrides.

Rule-based Constraints & Multi-Objective Optimization: Balance service readiness, reliability, cost, and branding exposure.

Ranked Induction Lists: Generate priority train schedules with explainable reasoning and conflict alerts.

“What-if” Simulations: Test alternative scenarios for operational planning.

Machine Learning Feedback Loops: Learn from historical outcomes to improve forecast accuracy over time.

🚀 Benefits

Data-Driven Decision Making: Replaces manual reconciliation with a reproducible, auditable process.

Higher Fleet Availability: Ensure more trains are ready for service.

Reduced Lifecycle Costs: Minimize component fatigue and maintenance expenses.

Enhanced Passenger Experience: Improved punctuality and smoother operations.

Empowered Operations Staff: Focus on strategic exceptions rather than routine data wrangling.

🛠️ Tech Stack

Backend: Python, Flask/FastAPI

Optimization: PuLP / OR-Tools / Custom ML Models

Database: PostgreSQL / MongoDB (for Maximo & IoT integration)

Frontend: ReactJS / Dash (for dashboards and simulations)

Visualization: Plotly, D3.js, or Highcharts

📂 Repository Structure
├── backend/        # API & optimization engine
├── frontend/       # Dashboard and UI
├── data/           # Sample datasets & historical records
├── docs/           # Project documentation & diagrams
├── models/         # ML models & training scripts
├── scripts/        # ETL, preprocessing, and automation scripts
└── README.md       # Project overview

🔗 References

KMRL Official Website

IBM Maximo Documentation

OR-Tools & PuLP Documentation

🤝 Contribution

We welcome contributions from developers, data scientists, and transport planners. Please read CONTRIBUTING.md before submitting pull requests.

🏆 License

This project is licensed under the MIT License – see LICENSE for details.
