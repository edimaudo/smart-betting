(function () {
  "use strict";

  // Readiness thresholds (PRD section 7). Kept as a single configurable
  // object so this can later be wired to a server-provided setting.
  var THRESHOLDS = {
    ready: 0.80,       // 80–100% -> Ready for Learner Simulator
    developing: 0.60,  // 60–79%  -> Developing
  };

  var QUESTIONS = [
    {
      question: "What does a bet's price primarily represent, beyond a potential payout?",
      options: [
        "A guarantee that the outcome will happen",
        "The break-even (implied) probability of that outcome",
        "The sportsbook's confidence in a team",
        "The amount of money already wagered"
      ],
      answer: 1,
      explanation: "Every price implies a break-even probability — the win rate at which the bet would neither profit nor lose money over time."
    },
    {
      question: "Decimal odds of 3.00 on a $20 stake return how much in total if the bet wins?",
      options: ["$20", "$40", "$60", "$80"],
      answer: 2,
      explanation: "Potential return = stake × decimal odds = 20 × 3.00 = $60 total (this includes the returned stake, so profit is $40)."
    },
    {
      question: "American odds of −150 mean:",
      options: [
        "A $150 stake wins $100 profit",
        "A $100 stake wins $150 profit",
        "The bet is not available",
        "A push always occurs"
      ],
      answer: 0,
      explanation: "Negative American odds show the stake needed to profit $100 — here, $150 staked profits $100 (implied probability 60%)."
    },
    {
      question: "Why does the sum of implied probabilities across a market's selections usually exceed 100%?",
      options: [
        "Because probability math is approximate",
        "Because of the bookmaker's built-in margin (the vig)",
        "Because every outcome is equally likely",
        "Because odds only apply to favorites"
      ],
      answer: 1,
      explanation: "The excess above 100% is the bookmaker's margin — often called the vig or juice — built into the odds rather than charged separately."
    },
    {
      question: "\"Edge\" in this application is best defined as:",
      options: [
        "The favorite in a matchup",
        "Model probability minus market (de-vigged) implied probability",
        "The sportsbook's profit margin",
        "The number of sportsbooks offering a price"
      ],
      answer: 1,
      explanation: "Edge = Model Probability − Market Probability. A positive edge means your model sees the outcome as more likely than the market's price implies."
    },
    {
      question: "A bet can have positive expected value and still lose money on any single attempt. Why?",
      options: [
        "Expected value calculations are usually wrong",
        "EV describes the long-run average outcome, not any individual result",
        "Sportsbooks void positive-EV bets",
        "EV only applies to parlays"
      ],
      answer: 1,
      explanation: "Expected value is an average over many repetitions. Variance means any single bet can still lose even when the long-run average is favorable."
    },
    {
      question: "Which of these is required before you can reliably remove (de-vig) a market's margin?",
      options: [
        "A minimum stake of one unit",
        "Odds for every selection in that market",
        "At least three competing sportsbooks",
        "A closing line"
      ],
      answer: 1,
      explanation: "Proportional de-vigging normalizes each selection's implied probability against the sum of ALL selections in the market — partial market data isn't enough."
    },
    {
      question: "The \"closing line\" refers to:",
      options: [
        "The first price ever posted for an event",
        "The final price available before the event starts",
        "The average price across the whole season",
        "A price only available after the event ends"
      ],
      answer: 1,
      explanation: "The closing line is the last available price before start time, and is widely treated as the market's most information-efficient estimate."
    },
    {
      question: "In backtesting, why must a strategy only use information available at the time of the simulated decision?",
      options: [
        "To make the backtest run faster",
        "To avoid look-ahead bias, which would overstate performance",
        "Because historical odds are never accurate",
        "It isn't necessary if the sample size is large"
      ],
      answer: 1,
      explanation: "Using future odds, outcomes, or closing prices when testing an earlier decision point is look-ahead bias — it inflates backtested performance in a way that wouldn't have been achievable in real time."
    },
    {
      question: "This application's core principle is best summarized as:",
      options: [
        "Always bet on the statistical favorite",
        "Predict the winner as accurately as possible",
        "Evaluate whether the available price justifies taking the risk",
        "Maximize the number of bets placed"
      ],
      answer: 2,
      explanation: "The product principle is explicit: don't just predict who will win — evaluate whether the price on offer justifies the risk, given edge, expected value, and confidence."
    }
  ];

  var state = { index: 0, score: 0, answered: false };

  var els = {};

  function q(sel) { return document.querySelector(sel); }

  function renderQuestion() {
    var item = QUESTIONS[state.index];
    state.answered = false;

    els.progressLabel.textContent = "Question " + (state.index + 1) + " of " + QUESTIONS.length;
    els.progressScore.textContent = "Score: " + state.score;
    els.progressFill.style.width = (((state.index) / QUESTIONS.length) * 100) + "%";

    els.questionText.textContent = item.question;
    els.options.innerHTML = "";
    els.feedback.hidden = true;
    els.nextBtn.disabled = true;
    els.nextBtn.textContent = (state.index === QUESTIONS.length - 1) ? "See results" : "Next question";

    item.options.forEach(function (optionText, i) {
      var li = document.createElement('li');
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'quiz-option';
      btn.textContent = optionText;
      btn.setAttribute('aria-pressed', 'false');
      btn.addEventListener('click', function () { selectOption(i, btn); });
      li.appendChild(btn);
      els.options.appendChild(li);
    });
  }

  function selectOption(i, btn) {
    if (state.answered) return; // one answer per question — no changing after submit
    state.answered = true;

    var item = QUESTIONS[state.index];
    var correct = i === item.answer;
    if (correct) state.score += 1;

    Array.prototype.forEach.call(els.options.querySelectorAll('.quiz-option'), function (b, idx) {
      b.disabled = true;
      b.setAttribute('aria-pressed', String(idx === i));
      if (idx === item.answer) b.classList.add('correct');
      else if (idx === i) b.classList.add('incorrect');
    });

    els.feedback.hidden = false;
    els.feedback.classList.toggle('correct', correct);
    els.feedback.classList.toggle('incorrect', !correct);
    els.feedbackTitle.textContent = correct ? "Correct." : "Not quite.";
    els.feedbackExplanation.textContent = item.explanation;

    els.progressScore.textContent = "Score: " + state.score;
    els.nextBtn.disabled = false;
  }

  function next() {
    if (state.index < QUESTIONS.length - 1) {
      state.index += 1;
      renderQuestion();
    } else {
      showResult();
    }
  }

  function classify(pct) {
    if (pct >= THRESHOLDS.ready) {
      return {
        label: "Ready for Learner Simulator",
        cls: "badge-signal",
        note: "You're ready to apply these concepts in the Learner Simulator — realistic scenarios with no real money involved."
      };
    }
    if (pct >= THRESHOLDS.developing) {
      return {
        label: "Developing",
        cls: "badge-warn",
        note: "You've got the basics. Review the sections you missed in Learn before moving on to the simulator."
      };
    }
    return {
      label: "Review Required",
      cls: "badge-fade",
      note: "Revisit the Learn section before progressing — especially odds conversion, implied probability, and edge."
    };
  }

  function showResult() {
    els.progressFill.style.width = "100%";
    q('#quiz-question-view').hidden = true;
    els.resultView.hidden = false;

    var pct = state.score / QUESTIONS.length;
    els.finalScore.textContent = state.score + " / " + QUESTIONS.length + " (" + Math.round(pct * 100) + "%)";

    var result = classify(pct);
    els.classification.textContent = result.label;
    els.classification.className = "quiz-classification badge " + result.cls;
    els.classificationNote.textContent = result.note;
    els.simulatorLink.setAttribute('aria-disabled', String(pct < THRESHOLDS.ready));
  }

  function retry() {
    state = { index: 0, score: 0, answered: false };
    els.resultView.hidden = true;
    q('#quiz-question-view').hidden = false;
    renderQuestion();
  }

  document.addEventListener('DOMContentLoaded', function () {
    els.progressLabel = q('#quiz-progress-label');
    els.progressScore = q('#quiz-progress-score');
    els.progressFill = q('#quiz-progress-fill');
    els.questionText = q('#quiz-question-text');
    els.options = q('#quiz-options');
    els.feedback = q('#quiz-feedback');
    els.feedbackTitle = q('#quiz-feedback-title');
    els.feedbackExplanation = q('#quiz-feedback-explanation');
    els.nextBtn = q('#quiz-next-btn');
    els.resultView = q('#quiz-result-view');
    els.finalScore = q('#quiz-final-score');
    els.classification = q('#quiz-classification');
    els.classificationNote = q('#quiz-classification-note');
    els.simulatorLink = q('#quiz-simulator-link');
    els.retryBtn = q('#quiz-retry-btn');

    els.nextBtn.addEventListener('click', next);
    els.retryBtn.addEventListener('click', retry);

    renderQuestion();
  });
})();
