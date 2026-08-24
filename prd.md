# Smart Betting — Product Requirements Document

## 1. Product Overview

Smart Betting is a sports betting education, analytics, simulation, and decision-support application.

The product is designed to help users move through a structured process:

1. Learn betting concepts
2. Validate their understanding
3. Practice interpreting real-world betting scenarios
4. Explore current betting markets
5. Analyze historical and current data
6. Apply mathematical models
7. Simulate potential outcomes
8. Determine whether a betting opportunity is worth considering

The product is a decision-support system, not a guarantee of betting outcomes.

---

## 2. Product Objective

Help users make more structured and evidence-based betting decisions by connecting:

- Betting education
- Market data
- Historical data
- Probability
- Odds
- Mathematical models
- Simulation
- Risk analysis
- Decision rules

The core product principle is:

> Do not simply predict who will win. Evaluate whether the available price justifies taking the risk.

---

## 3. Target Users

### Primary

Users who:

- Want to understand sports betting
- Want to analyze betting markets quantitatively
- Want to test strategies before using real money
- Want structured decision support
- Have varying levels of betting knowledge

### Secondary

More experienced users who want:

- Historical data
- Odds analysis
- Model outputs
- Backtesting
- Strategy comparison
- Decision rules

---

# 4. Product Architecture

The application consists of eight primary areas:

1. Overview
2. Learn
3. Markets
4. Data History
5. Analyze
6. Strategies
7. Simulate
8. Decide

The data layer supports all analytical components.

---

# 5. Overview

## Purpose

Provide a high-level view of the betting environment.

## Requirements

The Overview should display:

- Current sporting events
- Upcoming events
- Sports
- Betting markets
- Current odds
- Market movement where available
- Basic analytical indicators
- Potential opportunities identified by the analysis engine

Users should be able to filter by:

- Sport
- League
- Date
- Event
- Market type

The Overview should not attempt to perform the full analysis.

It should act as the user's entry point into the system.

---

# 6. Learn

## Purpose

Teach users the concepts required to understand the rest of the application.

## Content Areas

### Betting Overview

Explain:

- What betting is
- How sportsbooks work
- How betting markets work
- How odds work
- How payouts work
- Probability
- Implied probability
- Bookmaker margin

### Key Terms

Provide a searchable glossary including:

- Moneyline
- Spread
- Total
- Over/Under
- Prop
- Parlay
- Decimal odds
- American odds
- Implied probability
- Vig / juice
- Bankroll
- Unit
- Edge
- Expected value
- Closing line
- Line movement
- Push

### Betting Approaches

Explain:

- Fundamental analysis
- Statistical analysis
- Market-based analysis
- Trend-based analysis
- Value-based analysis
- Model-driven analysis
- Risk-based approaches

### Upsides and Downsides

Explain:

- Analytical benefits
- Financial risk
- Variance
- Model error
- Data limitations
- Behavioral risks
- Overconfidence

### Strategic Thinking

Teach users to evaluate:

`Probability → Odds → Implied Probability → Edge → Expected Value → Risk`

---

# 7. Learning Quiz

## Purpose

Validate whether the user understands the core concepts before entering the learner simulator.

## Requirements

The quiz must contain:

- 10 questions
- One question displayed at a time
- Multiple-choice answers
- Immediate answer feedback
- Explanation of the correct answer
- Score calculation

## Readiness Threshold

### 80–100%

User is considered:

**Ready for Learner Simulator**

### 60–79%

User is considered:

**Developing**

User should be encouraged to review the relevant learning content.

### Below 60%

User is considered:

**Review Required**

User should review the Learn section before progressing.

The threshold should eventually be configurable.

---

# 8. Learner Simulator

## Purpose

Allow users to apply betting concepts to realistic scenarios without requiring real-money betting.

## Requirements

The simulator should present real-world-style betting scenarios containing:

- Sport
- Event
- Market
- Odds
- Available outcomes
- Relevant information
- Historical information where appropriate

The user should be asked to determine:

- Implied probability
- Potential payout
- Potential edge
- Expected value
- Whether the bet appears attractive

The system should then reveal:

- Correct calculations
- Relevant market information
- Outcome
- Explanation

The learner simulator is educational and should not require real-money wagering.

---

# 9. Markets

## Purpose

Provide current and upcoming betting market information.

## Requirements

Markets should include:

- Sport
- League
- Event
- Event start time
- Market type
- Selection
- Odds
- Sportsbook/source
- Timestamp

Users should be able to filter by:

- Sport
- League
- Market
- Date
- Event
- Odds range
- Sportsbook

The application should distinguish between:

- Current odds
- Historical odds
- Opening odds
- Closing odds

where the underlying data supports those distinctions.

---

# 10. Data Layer

## Purpose

Provide normalized data from external sports and betting APIs.

## Requirements

The system should support external data providers through a provider abstraction.

The application should not tightly couple the analysis engine to a single API.

Each provider should normalize data into the application's internal format.

Core entities include:

- Sport
- League
- Team
- Player
- Event
- Market
- Selection
- Odds
- Sportsbook
- Odds timestamp
- Event outcome

The system should preserve the source and timestamp for imported data.

---

# 11. Historical Data

## Purpose

Provide the historical dataset required for analysis and model validation.

## Requirements

Users should be able to filter historical data by:

- Sport
- League
- Date
- Team
- Player
- Market
- Sportsbook
- Odds
- Outcome
- Season
- Strategy

The system should support historical odds where available.

Historical data must preserve timestamps to prevent look-ahead bias during backtesting.

---

# 12. Analysis

## Purpose

Convert market and historical data into analytical signals.

## Core Calculations

The system should support:

### Implied Probability

Convert odds into the probability represented by the market price.

### Vig Adjustment

Where sufficient market information exists, estimate the bookmaker margin and normalize probabilities.

### Edge

Compare model probability with market-implied probability.

Example:

`Edge = Model Probability - Market Probability`

### Expected Value

Calculate expected return based on:

- Estimated probability
- Odds
- Stake

### Expected Payout

Calculate potential return based on:

- Stake
- Odds
- Outcome

### Variance / Risk

Where sufficient data exists, estimate:

- Historical variance
- Probability of loss
- Drawdown
- Losing streaks

---

# 13. Mathematical Models

The system should support multiple analytical models rather than a single prediction model.

Initial model categories may include:

- Historical frequency
- Rolling averages
- Team/player performance
- Probability models
- Regression models
- Elo-style ratings
- Market-implied models
- Monte Carlo simulation

Models should produce:

- Estimated probability
- Confidence
- Expected outcome
- Model assumptions

Model outputs should be stored separately from raw market data.

---

# 14. Strategy Layer

## Purpose

Allow users to define and evaluate betting strategies.

A strategy should contain:

- Strategy name
- Sport
- Market
- Entry conditions
- Probability threshold
- Minimum edge
- Minimum expected value
- Stake rule
- Risk constraints
- Historical evaluation period

Example:

```text
Sport: NBA
Market: Moneyline
Minimum Edge: 5%
Minimum EV: Positive
Minimum Model Confidence: 70%
Stake: 1 unit

15. Simulation
Purpose
Determine how models and strategies perform under repeated scenarios.
Requirements
Simulation should support:
Historical backtesting
Probability-based simulation
Monte Carlo simulation
Strategy testing
Stake testing
Outputs should include:
Total return
ROI
Win rate
Loss rate
Maximum drawdown
Profit distribution
Losing streak
Average return
Expected return
The system must clearly distinguish historical backtesting from simulated future outcomes.
16. Decision Layer
Purpose
Determine whether an opportunity passes predefined analytical criteria.
The Decision Layer is the final analytical gate between an identified opportunity and a potential betting decision.
Decision Inputs
The decision engine should consider:
Market odds
Implied probability
Model probability
Edge
Expected value
Model confidence
Historical performance
Market liquidity where available
Odds movement
Data quality
Strategy fit
Risk
Stake size
Decision Output
The system should classify an opportunity into categories such as:
Strong Candidate
Opportunity meets all major criteria.
Candidate
Opportunity meets most criteria but has limitations.
Weak Candidate
Some evidence exists but value or confidence is insufficient.
Pass
Opportunity does not meet the decision criteria.
Insufficient Data
The system does not have enough reliable information to make an assessment.
The decision layer should explain why a decision was reached.
Example:
Decision: PASS

Model probability: 52%
Market probability: 50%
Edge: 2%

Minimum required edge: 5%

Reason:
The estimated edge is below the strategy threshold.
The system must not represent the decision as a guaranteed prediction.
17. User Experience
Design Principles
The application should be:
Analytical
Minimal
Clear
Data-focused
Responsive
Accessible
The application should avoid excessive text inside analytical interfaces.
18. Accessibility
The application must target WCAG 2.1 AA.
Requirements include:
Keyboard navigation
Visible focus states
Semantic HTML
Appropriate heading hierarchy
Accessible labels
Sufficient color contrast
No color-only information
Screen-reader-friendly controls
Responsive layouts
Reduced-motion support
19. Typography
Primary font:
Inter
Font sizing must support:
Small
Medium
Large
Default:
Medium
Changing the font size should scale text and associated UI elements proportionally.
20. Theme
The application must support:
Dark mode
Light mode
Default:
Dark mode
Theme changes must maintain:
Readability
Contrast
Visible controls
Consistent hierarchy
WCAG compliance
21. Responsive Design
The application must support:
Desktop
Tablet
Mobile
Navigation and data-heavy interfaces should adapt rather than simply shrink.
Tables should use responsive behavior appropriate to the information density.
22. Responsible Product Design
The application should clearly communicate that betting involves financial risk.
The product should emphasize:
Education
Analysis
Risk
Uncertainty
Probability
Responsible decision-making
The system should not claim that a model can guarantee winning outcomes.
23. MVP Scope
The MVP should include:
Phase 1
FastAPI application
Jinja2 templates
Responsive UI
Theme switching
Font-size controls
Overview
Learn
Glossary
10-question quiz
Phase 2
Learner simulator
Sports/event data model
API integration
Markets page
Historical data storage
Phase 3
Probability calculations
Odds conversion
Edge
Expected value
Analysis interface
Phase 4
Strategies
Backtesting
Simulation
Decision engine
Phase 5
Multiple data providers
Advanced models
Advanced analytics
Strategy optimization

### `requirements.md`

```markdown
# Smart Betting — Technical Requirements

## 1. Technology Stack

### Backend

- Python 3.11+
- FastAPI
- Uvicorn
- Jinja2

### Frontend

- HTML5
- CSS3
- Vanilla JavaScript
- Inter font

### Initial Architecture

Server-rendered application using:

```text
FastAPI
   ↓
Jinja2
   ↓
HTML / CSS / JavaScript
The MVP should avoid introducing a frontend framework unless there is a demonstrated requirement.
2. Application Structure
The application should use the following structure:
smart_betting/
│
├── main.py
├── requirements.txt
├── requirements.md
├── prd.md
│
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── learn.html
│   ├── quiz.html
│   ├── markets.html
│   ├── history.html
│   ├── analyze.html
│   ├── strategies.html
│   ├── simulate.html
│   └── decide.html
│
├── static/
│   ├── css/
│   │   └── app.css
│   │
│   └── js/
│       └── app.js
│
├── app/
│   ├── models/
│   ├── services/
│   ├── calculations/
│   ├── strategies/
│   ├── simulation/
│   ├── decision/
│   └── data/
│
└── tests/
3. FastAPI Requirements
The application must:
Initialize a FastAPI application
Mount static assets
Configure Jinja2
Provide route handlers
Return HTML responses
Support future API endpoints
Initial routes:
GET /
GET /learn
GET /learn/quiz
GET /markets
GET /history
GET /analyze
GET /strategies
GET /simulate
GET /decide
4. Frontend Requirements
Base Template
base.html must provide:
Global navigation
Page title
Font loading
Theme controls
Font-size controls
Main content block
Accessibility features
All pages should inherit from the base template.
5. Navigation
Navigation must expose:
Overview
Learn
Markets
History
Analyze
Strategies
Simulate
Decide
The current page must have a visually distinguishable active state.
Navigation must be keyboard accessible.
6. Theme System
Theme state must be stored in the browser.
Supported values:
dark
light
Default:
dark
The application should use CSS custom properties rather than duplicating component styles for each theme.
Example:
:root {
    --bg: ...;
    --surface: ...;
    --text: ...;
    --border: ...;
    --accent: ...;
}
Theme switching must update these variables.
7. Font Scaling
Supported values:
small
medium
large
Default:
medium
Initial scaling:
small: 90%
medium: 100%
large: 115%
Scaling should use a root CSS variable so that typography and UI spacing can scale consistently.
Example:
html[data-font-size="small"] {
    --scale: 0.9;
}

html[data-font-size="medium"] {
    --scale: 1;
}

html[data-font-size="large"] {
    --scale: 1.15;
}
The setting must persist across page navigation.
8. Accessibility Requirements
Target:
WCAG 2.1 AA
The implementation must provide:
Semantic HTML
Keyboard navigation
Visible focus indicators
Accessible labels
Proper form controls
aria-live for dynamic quiz feedback
Correct heading hierarchy
Adequate contrast
Responsive text
Reduced-motion support
Interactive controls must have a minimum usable touch/click target.
9. Learn Module
The Learn module must be implemented as static content initially.
Required sections:
Betting Overview
Key Terms
Approaches
Upsides & Downsides
Strategic Thinking
Knowledge Quiz
The glossary must support client-side search.
Glossary terms should be represented as structured HTML so that they can later be migrated into a database or content model.
10. Quiz Requirements
The quiz should initially run entirely client-side.
Question structure:
{
    question: "...",
    options: [
        "...",
        "...",
        "...",
        "..."
    ],
    answer: 0,
    explanation: "..."
}
Requirements:
Exactly 10 questions
One question displayed at a time
Four answer options
Immediate feedback
Correct answer highlighted
Incorrect answer highlighted when selected
Explanation displayed
Score calculated
Final readiness classification
Classification:
80–100% → Ready for Learner Simulator
60–79%  → Developing
0–59%   → Review Required
The quiz must not allow users to select multiple answers.
11. Learner Simulator Requirements
The simulator should eventually use structured scenario objects.
Example:
{
    "sport": "NBA",
    "event": "...",
    "market": "Moneyline",
    "selection": "...",
    "odds": -110,
    "context": "...",
    "question": "..."
}
The simulator should test:
Odds interpretation
Payout calculation
Implied probability
Probability comparison
Edge
Expected value
Decision reasoning
The simulator must not require real-money execution.
12. Data Model
The system should eventually support the following entities.
Sport
id
name
League
id
sport_id
name
Team
id
league_id
name
Player
id
team_id
name
Event
id
sport_id
league_id
home_team_id
away_team_id
start_time
status
Market
id
event_id
market_type
name
Selection
id
market_id
name
Odds
id
selection_id
sportsbook
price
timestamp
Outcome
id
event_id
selection_id
result
timestamp
13. Data Provider Architecture
External sports and betting APIs must be isolated behind provider interfaces.
Example:
class SportsDataProvider:
    async def get_events(self):
        ...

    async def get_odds(self):
        ...

    async def get_historical_data(self):
        ...
The application should normalize external provider responses into internal models.
The analysis engine must operate on normalized internal data rather than provider-specific structures.
14. Data Quality
Imported records should retain:
Provider
Provider event ID
Provider market ID
Timestamp
Retrieval timestamp
The system must avoid silently overwriting historical odds.
Historical odds should be append-oriented where possible.
15. Odds Calculations
The calculation layer must support:
Decimal Odds
Potential Return = Stake × Decimal Odds
Decimal Implied Probability
Implied Probability = 1 / Decimal Odds
American Odds
Positive:
Implied Probability =
100 / (American Odds + 100)
Negative:
Implied Probability =
- American Odds / (- American Odds + 100)
The calculation layer must be independently testable.
16. Edge Calculation
The system must support:
Edge =
Model Probability - Market Implied Probability
The calculation should preserve precision internally.
Display precision may be configurable.
17. Expected Value
For a binary outcome:
EV =
(P(win) × Profit)
-
(P(loss) × Stake)
The implementation must clearly distinguish:
Expected profit
Total payout
Stake
Return
18. Vig / Market Margin
Where all relevant market outcomes are available:
Raw Market Probability =
sum(implied probabilities)
The system should be able to calculate the market overround.
Where appropriate:
Normalized Probability =
Individual Implied Probability / Total Implied Probability
The implementation should document assumptions because margin-removal methods can differ by market.
19. Analysis Engine
The analysis engine should accept:
market data
historical data
model probability
market probability
strategy parameters
and produce:
implied probability
model probability
edge
expected value
confidence
risk metrics
The analysis engine must not directly access external APIs.
20. Model Interface
Models should implement a common interface.
Example:
class BettingModel:
    def predict(self, data):
        raise NotImplementedError
Model output:
{
    "probability": 0.57,
    "confidence": 0.72,
    "model_name": "Example Model"
}
Models must expose their assumptions.
21. Strategy Engine
Strategies should be represented as configurable rules.
Example:
{
    "min_edge": 0.05,
    "min_ev": 0,
    "min_confidence": 0.70,
    "max_stake_units": 2
}
The strategy engine should evaluate whether an opportunity meets its rules.
22. Simulation Engine
The simulation engine must support:
Backtesting
Historical sequence:
Historical data
      ↓
Strategy
      ↓
Historical decisions
      ↓
Historical outcomes
      ↓
Performance
Monte Carlo
Simulation sequence:
Probability distribution
      ↓
Randomized trials
      ↓
Repeated outcomes
      ↓
Distribution of results
Simulation outputs should include:
Expected return
Median return
ROI
Win rate
Maximum drawdown
Worst-case scenarios
Losing streaks
23. Look-Ahead Bias Prevention
Backtesting must only use information that would have been available at the time of the simulated decision.
The system must not use:
Future odds
Future outcomes
Future player/team information
Closing prices when testing an earlier decision point
unless explicitly testing a strategy that is defined to use those values.
This is a critical requirement.
24. Decision Engine
The decision engine must evaluate an opportunity using configurable criteria.
Example:
decision = {
    "model_probability": 0.56,
    "market_probability": 0.51,
    "edge": 0.05,
    "expected_value": 0.08,
    "confidence": 0.74,
    "risk": "medium"
}
The engine should return:
decision
classification
reasons
failed criteria
supporting metrics
Example:
{
    "classification": "PASS",
    "reasons": [
        "Edge below minimum threshold",
        "Model confidence below threshold"
    ]
}
The engine must support an explicit:
INSUFFICIENT_DATA
state.
25. Decision Rules
The initial decision framework should evaluate:
Is the data sufficient?
Is the market price available?
Is the model probability available?
Is there an estimated edge?
Is expected value positive?
Does the opportunity meet the selected strategy?
Is model confidence sufficient?
Is historical evidence sufficient?
Is the risk acceptable?
The system should not automatically classify a bet as attractive solely because EV is positive.
26. Stake Calculation
Stake sizing should be separated from opportunity evaluation.
The application should eventually support:
Fixed unit
Percentage bankroll
Kelly-style sizing
Fractional Kelly
Stake recommendations must be presented as analytical outputs rather than guarantees.
27. Database
The MVP may begin without a database for static content.
Once market and historical data are introduced, a persistent database is required.
Recommended initial option:
PostgreSQL
The database should support:
Historical records
Time-series odds
Sports
Events
Markets
Strategies
Model outputs
Simulation results
28. API Layer
Internal API endpoints should eventually expose:
/api/sports
/api/events
/api/markets
/api/odds
/api/history
/api/analyze
/api/strategies
/api/simulations
/api/decisions
HTML routes and API routes should remain conceptually separate.
29. Testing Requirements
The project must include automated tests for:
Unit Tests
Odds conversion
Implied probability
Vig calculations
Edge
EV
Stake calculations
Decision rules
Integration Tests
API provider normalization
Database persistence
Historical data retrieval
Analysis pipeline
Backtesting Tests
No look-ahead bias
Correct chronological ordering
Correct stake calculation
Correct return calculation
30. Security
The application should:
Validate external data
Validate user inputs
Avoid arbitrary code execution
Store API credentials outside source code
Use environment variables for secrets
Avoid exposing provider credentials to the browser
Example:
SPORTS_API_KEY=
DATABASE_URL=
31. Configuration
Configuration should eventually be centralized.
Example:
class Settings:
    sports_api_key: str
    database_url: str
Environment-specific configuration must not be hard-coded.
32. Performance
The application should:
Avoid unnecessary API calls
Cache relatively static data
Normalize provider data once
Use asynchronous API calls where appropriate
Avoid recalculating historical models unnecessarily
Data ingestion and analysis should eventually run independently from page rendering.
33. MVP Acceptance Criteria
The first MVP is considered complete when:
FastAPI application starts successfully
All primary routes work
Jinja2 templates render
Navigation works
Responsive layout works
Inter is used
Dark/light mode works
Font-size controls work
Learn content is available
Glossary search works
Quiz contains 10 questions
Quiz calculates score
Quiz produces readiness classification
No accessibility-critical interaction requires a mouse
34. Development Sequence
Development should proceed in this order:
Step 1 — Foundation
FastAPI
Jinja2
Static assets
Base template
Navigation
Theme
Typography
Responsive layout
Step 2 — Learning
Learn page
Glossary
Quiz
Readiness classification
Step 3 — Data Foundation
Data models
Database
Provider abstraction
Sports/event ingestion
Step 4 — Markets
Current markets
Odds
Filters
Event details
Step 5 — Historical Data
Historical ingestion
Storage
Filtering
Data exploration
Step 6 — Analysis
Odds calculations
Probability
Edge
EV
Model framework
Step 7 — Strategies
Strategy definitions
Rules
Strategy evaluation
Step 8 — Simulation
Backtesting
Monte Carlo
Performance metrics
Step 9 — Decision Layer
Decision rules
Evidence scoring
Risk assessment
Decision explanation
Step 10 — Validation
Automated tests
Model validation
Backtesting validation
Accessibility testing
Responsive testing