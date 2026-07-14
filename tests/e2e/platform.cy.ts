// ============================================================
// KMRL NexusAI — Cypress E2E Test Suite
// ============================================================
// Run: npx cypress run --spec "tests/e2e/**/*.cy.ts"

// ── Auth Flow ─────────────────────────────────────────────────────────────
describe('Authentication', () => {
  beforeEach(() => { cy.visit('/') })

  it('redirects unauthenticated users to login', () => {
    cy.url().should('include', '/login')
  })

  it('shows error on invalid credentials', () => {
    cy.visit('/login')
    cy.get('[data-cy=email]').type('wrong@kmrl.in')
    cy.get('[data-cy=password]').type('wrongpassword')
    cy.get('[data-cy=login-btn]').click()
    cy.get('[data-cy=error-msg]').should('contain', 'Invalid')
  })

  it('logs in successfully with valid credentials', () => {
    cy.visit('/login')
    cy.get('[data-cy=email]').type('depot_controller@kmrl.in')
    cy.get('[data-cy=password]').type('kmrl@2025')
    cy.get('[data-cy=login-btn]').click()
    cy.url().should('include', '/dashboard')
    cy.get('[data-cy=topbar]').should('be.visible')
  })

  it('logs out and clears session', () => {
    cy.login('depot_controller@kmrl.in', 'kmrl@2025')
    cy.get('[data-cy=user-menu]').click()
    cy.get('[data-cy=logout-btn]').click()
    cy.url().should('include', '/login')
    cy.window().its('localStorage').invoke('getItem', 'kmrl_token').should('be.null')
  })
})

// ── Command Center Dashboard ───────────────────────────────────────────────
describe('Command Center Dashboard', () => {
  beforeEach(() => { cy.login() })

  it('renders all KPI tiles', () => {
    cy.visit('/dashboard')
    cy.get('[data-cy=kpi-availability]').should('be.visible')
    cy.get('[data-cy=kpi-revenue]').should('be.visible')
    cy.get('[data-cy=kpi-confidence]').should('be.visible')
    cy.get('[data-cy=kpi-shunting]').should('be.visible')
  })

  it('shows AI ticker message', () => {
    cy.visit('/dashboard')
    cy.get('[data-cy=ai-ticker]').should('be.visible')
  })

  it('displays WebSocket connection status', () => {
    cy.visit('/dashboard')
    cy.get('[data-cy=ws-status]', { timeout: 10_000 }).should('be.visible')
  })

  it('shows fleet mileage heatmap', () => {
    cy.visit('/dashboard')
    cy.get('[data-cy=mileage-heatmap]').should('be.visible')
    cy.get('[data-cy=mileage-heatmap] > div').should('have.length.at.least', 25)
  })

  it('refreshes KPIs on button click', () => {
    cy.visit('/dashboard')
    cy.intercept('GET', '/api/v1/kpis').as('kpis')
    cy.get('[data-cy=refresh-btn]').click()
    cy.wait('@kpis')
  })
})

// ── Optimizer ────────────────────────────────────────────────────────────
describe('AI Optimizer', () => {
  beforeEach(() => { cy.login() })

  it('runs optimizer and shows plan', () => {
    cy.visit('/dashboard')
    cy.intercept('POST', '/api/v1/induction/optimize').as('optimize')
    cy.get('[data-cy=run-optimizer]').click()
    cy.get('[data-cy=run-optimizer]').should('contain', 'Running')
    cy.wait('@optimize', { timeout: 45_000 })
    cy.get('[data-cy=ai-ticker]').should('contain', 'revenue service')
  })

  it('displays AI recommendation cards after optimization', () => {
    cy.visit('/dashboard')
    cy.intercept('POST', '/api/v1/induction/optimize', { fixture: 'induction_plan.json' }).as('optimize')
    cy.get('[data-cy=run-optimizer]').click()
    cy.wait('@optimize')
    cy.get('[data-cy=ai-rec-card]').should('have.length.at.least', 1)
  })

  it('shows confidence percentage on each recommendation', () => {
    cy.visit('/dashboard')
    cy.intercept('POST', '/api/v1/induction/optimize', { fixture: 'induction_plan.json' })
    cy.get('[data-cy=run-optimizer]').click()
    cy.get('[data-cy=ai-rec-card]').first().within(() => {
      cy.get('[data-cy=confidence-ring]').should('be.visible')
      cy.get('[data-cy=confidence-value]').invoke('text').should('match', /\d+%/)
    })
  })

  it('expands reasoning on card click', () => {
    cy.visit('/dashboard')
    cy.intercept('POST', '/api/v1/induction/optimize', { fixture: 'induction_plan.json' })
    cy.get('[data-cy=run-optimizer]').click()
    cy.get('[data-cy=ai-rec-card]').first().click()
    cy.get('[data-cy=ai-reasoning]').should('be.visible')
  })
})

// ── Fleet View ────────────────────────────────────────────────────────────
describe('Fleet Status', () => {
  beforeEach(() => { cy.login() })

  it('renders trainset cards', () => {
    cy.visit('/fleet')
    cy.get('[data-cy=trainset-card]', { timeout: 10_000 }).should('have.length.at.least', 20)
  })

  it('filters fleet by status', () => {
    cy.visit('/fleet')
    cy.get('[data-cy=status-filter]').select('revenue_service')
    cy.get('[data-cy=trainset-card]').each($el => {
      cy.wrap($el).find('[data-cy=status-badge]').should('contain', 'Revenue')
    })
  })

  it('shows health bars on each trainset card', () => {
    cy.visit('/fleet')
    cy.get('[data-cy=trainset-card]').first().within(() => {
      cy.get('[data-cy=health-bar-brake]').should('be.visible')
      cy.get('[data-cy=health-bar-hvac]').should('be.visible')
      cy.get('[data-cy=health-bar-door]').should('be.visible')
    })
  })

  it('flags trainsets with critical jobs', () => {
    cy.visit('/fleet')
    cy.get('[data-cy=critical-jobs-warning]').should('have.length.at.least', 1)
  })
})

// ── Depot Digital Twin ────────────────────────────────────────────────────
describe('Depot View', () => {
  beforeEach(() => { cy.login() })

  it('loads depot SVG layout', () => {
    cy.visit('/depot')
    cy.get('[data-cy=depot-svg]', { timeout: 10_000 }).should('be.visible')
  })

  it('shows bay occupancy count', () => {
    cy.visit('/depot')
    cy.get('[data-cy=occupied-bays]').should('contain', '/')
  })

  it('runs shunting simulation', () => {
    cy.visit('/depot')
    cy.intercept('POST', '/api/v1/depot/simulate').as('simulate')
    cy.get('[data-cy=run-simulation]').click()
    cy.wait('@simulate')
    cy.get('[data-cy=simulation-result]').should('be.visible')
  })

  it('shows shunting KPIs after simulation', () => {
    cy.visit('/depot')
    cy.intercept('POST', '/api/v1/depot/simulate', { fixture: 'simulation_result.json' })
    cy.get('[data-cy=run-simulation]').click()
    cy.get('[data-cy=reduction-pct]').should('be.visible')
    cy.get('[data-cy=ops-reduced]').should('be.visible')
  })
})

// ── Maintenance ───────────────────────────────────────────────────────────
describe('Maintenance Intelligence', () => {
  beforeEach(() => { cy.login() })

  it('loads predictive risk table', () => {
    cy.visit('/maintenance')
    cy.get('[data-cy=maintenance-table]', { timeout: 10_000 }).should('be.visible')
  })

  it('shows risk level for each trainset', () => {
    cy.visit('/maintenance')
    cy.get('[data-cy=risk-level]').should('have.length.at.least', 5)
  })

  it('flags high-risk trainsets in red', () => {
    cy.visit('/maintenance')
    cy.get('[data-cy=risk-critical]').should('have.length.at.least', 1)
  })

  it('opens job creation form', () => {
    cy.visit('/maintenance')
    cy.get('[data-cy=create-job-btn]').click()
    cy.get('[data-cy=job-form]').should('be.visible')
  })
})

// ── Alerts ────────────────────────────────────────────────────────────────
describe('Alerts & Incidents', () => {
  beforeEach(() => { cy.login() })

  it('shows alert list', () => {
    cy.visit('/alerts')
    cy.get('[data-cy=alert-item]', { timeout: 10_000 }).should('have.length.at.least', 1)
  })

  it('acknowledges an alert', () => {
    cy.visit('/alerts')
    cy.intercept('PATCH', '/api/v1/alerts/*/acknowledge').as('ack')
    cy.get('[data-cy=alert-item]').first().find('[data-cy=ack-btn]').click()
    cy.wait('@ack')
  })

  it('filters by severity', () => {
    cy.visit('/alerts')
    cy.get('[data-cy=severity-filter]').select('critical')
    cy.get('[data-cy=alert-item]').each($el => {
      cy.wrap($el).find('[data-cy=severity-badge]').should('contain', 'critical')
    })
  })
})

// ── Analytics ─────────────────────────────────────────────────────────────
describe('Analytics & KPIs', () => {
  beforeEach(() => { cy.login() })

  it('loads analytics page', () => {
    cy.visit('/analytics')
    cy.get('[data-cy=analytics-page]').should('be.visible')
  })

  it('renders availability trend chart', () => {
    cy.visit('/analytics')
    cy.get('[data-cy=availability-chart]', { timeout: 10_000 }).should('be.visible')
  })

  it('exports PDF report', () => {
    cy.visit('/analytics')
    cy.intercept('GET', '/api/v1/induction/plans/*/export').as('export')
    cy.get('[data-cy=export-pdf]').click()
    cy.get('[data-cy=export-success]').should('be.visible')
  })
})

// ── Accessibility ─────────────────────────────────────────────────────────
describe('Accessibility', () => {
  beforeEach(() => { cy.login() })

  it('keyboard shortcut Cmd+R triggers optimizer', () => {
    cy.visit('/dashboard')
    cy.get('body').type('{meta}r')
    cy.get('[data-cy=run-optimizer]').should('have.class', 'loading')
  })

  it('all interactive elements have accessible labels', () => {
    cy.visit('/dashboard')
    cy.get('button').each($btn => {
      const hasLabel = $btn.attr('aria-label') || $btn.text().trim().length > 0
      expect(hasLabel).to.be.true
    })
  })
})

// ── Cypress Commands ──────────────────────────────────────────────────────
// cypress/support/commands.ts

declare global {
  namespace Cypress {
    interface Chainable {
      login(email?: string, password?: string): Chainable<void>
    }
  }
}

Cypress.Commands.add('login', (
  email = 'depot_controller@kmrl.in',
  password = 'kmrl@2025',
) => {
  cy.request('POST', `${Cypress.env('apiUrl') ?? 'http://localhost:8000'}/api/v1/auth/token`, {
    username: email,
    password,
  }).then(res => {
    window.localStorage.setItem('kmrl_token', res.body.access_token)
    window.localStorage.setItem('kmrl_user', JSON.stringify({
      user_id: res.body.user_id,
      role: res.body.role,
    }))
  })
})
