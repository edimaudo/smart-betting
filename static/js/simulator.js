(function () {
  "use strict";

  // Structured scenario objects, matching the shape in requirements.md
  // section 11. These are illustrative and self-contained for the MVP;
  // a later iteration can source them from /api/analyze against live
  // mock-provider events instead of this fixed bank.
  var SCENARIOS = [
    {
      sport: "NBA", matchup: "Denver Nuggets @ Los Angeles Lakers", market: "Moneyline",
      selection: "Lakers (home)", odds: -135, stake: 10,
      context: "The Lakers are 3-point home favorites, both starting bigs are healthy, and they're on two extra days of rest. An independent model estimates LA's true win probability at 58%.",
      model_probability: 0.58, result: "win",
    },
    {
      sport: "NFL", matchup: "Buffalo Bills @ Miami Dolphins", market: "Moneyline",
      selection: "Bills (away)", odds: 120, stake: 10,
      context: "Miami is a slight home favorite, but Buffalo's defense ranks well against Miami's pass-heavy offense. A model puts Buffalo's win probability at 47%.",
      model_probability: 0.47, result: "loss",
    },
    {
      sport: "EPL", matchup: "Arsenal vs Newcastle United", market: "Moneyline",
      selection: "Arsenal (home)", odds: -180, stake: 10,
      context: "Arsenal is heavily favored at home against a Newcastle side missing two starting defenders. A model estimates Arsenal's win probability at 66%.",
      model_probability: 0.66, result: "win",
    },
    {
      sport: "NBA", matchup: "Milwaukee Bucks @ Boston Celtics", market: "Moneyline",
      selection: "Bucks (away)", odds: 145, stake: 10,
      context: "Boston is favored at home, but Milwaukee's star forward returns from a short absence. A model estimates Milwaukee's win probability at 41%.",
      model_probability: 0.41, result: "loss",
    },
    {
      sport: "NFL", matchup: "Dallas Cowboys @ Philadelphia Eagles", market: "Moneyline",
      selection: "Eagles (home)", odds: -110, stake: 10,
      context: "This is close to a pick'em on paper. A model that accounts for recent injuries estimates Philadelphia's win probability at 56%.",
      model_probability: 0.56, result: "win",
    },
  ];

  function americanToDecimal(american) {
    return american > 0 ? 1 + american / 100 : 1 + 100 / -american;
  }
  function impliedProbability(american) {
    return american > 0 ? 100 / (american + 100) : -american / (-american + 100);
  }
  function pct(x) { return (x * 100).toFixed(1) + "%"; }
  function money(x) { return (x < 0 ? "-$" : "$") + Math.abs(x).toFixed(2); }

  var idx = 0;
  var chosenAttractive = null;
  var els = {};

  function loadScenario() {
    var s = SCENARIOS[idx];
    els.progress.textContent = "Scenario " + (idx + 1) + " of " + SCENARIOS.length;
    els.context.textContent = s.sport + " · " + s.matchup + ". " + s.context;
    els.market.textContent = s.market;
    els.selection.textContent = s.selection;
    els.odds.textContent = (s.odds > 0 ? "+" : "") + s.odds;
    els.stake.textContent = money(s.stake);

    els.form.reset();
    els.form.hidden = false;
    els.reveal.classList.remove('visible');
    chosenAttractive = null;
    document.querySelectorAll('[data-attractive]').forEach(function (b) { b.setAttribute('aria-pressed', 'false'); });
  }

  function reveal() {
    var s = SCENARIOS[idx];
    var decimal = americanToDecimal(s.odds);
    var implied = impliedProbability(s.odds);
    var payout = s.stake * decimal;
    var profitIfWin = payout - s.stake;
    var edge = s.model_probability - implied;
    var ev = (s.model_probability * profitIfWin) - ((1 - s.model_probability) * s.stake);
    var attractive = edge > 0 && ev > 0;

    els.revealImplied.textContent = pct(implied);
    els.revealModel.textContent = pct(s.model_probability);
    els.revealEdge.textContent = (edge >= 0 ? "+" : "") + pct(edge);
    els.revealEv.textContent = money(ev);
    els.revealPayout.textContent = money(payout);

    var userCalledAttractive = chosenAttractive === 'yes';
    var matched = chosenAttractive !== null && userCalledAttractive === attractive;

    els.verdict.textContent = attractive
      ? "By this simple edge/EV check, the bet looks attractive."
      : "By this simple edge/EV check, the bet does not look attractive.";
    els.explanation.textContent =
      "Edge = model probability (" + pct(s.model_probability) + ") − implied probability (" + pct(implied) + ") = " +
      (edge >= 0 ? "+" : "") + pct(edge) + ". Expected value at a $" + s.stake.toFixed(2) + " stake is " + money(ev) + ". " +
      (chosenAttractive === null
        ? "You didn't select an answer, so there's nothing to compare here."
        : (matched ? "Your call matched this check." : "Your call didn't match this check. Compare your edge/EV math above to see why."));

    els.outcome.textContent = "In this fictional scenario, the selection actually " + (s.result === "win" ? "won" : "lost") +
      ". Remember: a single outcome never confirms or disproves whether a bet was well-reasoned. Only the price and probability at the time of the decision do.";

    els.form.hidden = true;
    els.reveal.classList.add('visible');
  }

  document.addEventListener('DOMContentLoaded', function () {
    els.progress = document.getElementById('sim-progress');
    els.context = document.getElementById('sim-context');
    els.market = document.getElementById('sim-market');
    els.selection = document.getElementById('sim-selection');
    els.odds = document.getElementById('sim-odds');
    els.stake = document.getElementById('sim-stake');
    els.form = document.getElementById('sim-form');
    els.reveal = document.getElementById('sim-reveal');
    els.revealImplied = document.getElementById('reveal-implied');
    els.revealModel = document.getElementById('reveal-model');
    els.revealEdge = document.getElementById('reveal-edge');
    els.revealEv = document.getElementById('reveal-ev');
    els.revealPayout = document.getElementById('reveal-payout');
    els.verdict = document.getElementById('reveal-verdict');
    els.explanation = document.getElementById('reveal-explanation');
    els.outcome = document.getElementById('reveal-outcome');

    document.querySelectorAll('[data-attractive]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        chosenAttractive = btn.getAttribute('data-attractive');
        document.querySelectorAll('[data-attractive]').forEach(function (b) {
          b.setAttribute('aria-pressed', String(b === btn));
        });
      });
    });

    els.form.addEventListener('submit', function (e) {
      e.preventDefault();
      reveal();
    });

    document.getElementById('sim-restart-btn').addEventListener('click', loadScenario);
    document.getElementById('sim-next-btn').addEventListener('click', function () {
      idx = (idx + 1) % SCENARIOS.length;
      loadScenario();
    });

    loadScenario();
  });
})();
