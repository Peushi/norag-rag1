import { useEffect, useState } from "react";

const STEPS = [
  "Reading your documents…",
  "Finding the right passages…",
  "Checking the sources…",
  "Writing your answer…",
];

/**
 * Shown while an answer is being written (usually 1 to 3 seconds): dough
 * rising in a bowl, with the step BakeFix is on. The rotating lines are for
 * sighted users only; screen readers hear one stable message, not four.
 */
export function BakingLoader() {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(
      () => setStep((current) => Math.min(current + 1, STEPS.length - 1)),
      1100,
    );
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="answer-placeholder baking-loader">
      <svg className="loader-bowl" viewBox="0 0 120 90" aria-hidden="true">
        <g className="loader-steam">
          <path d="M44 22c-4-6 4-10 0-16" />
          <path d="M60 18c-4-6 4-10 0-16" />
          <path d="M76 22c-4-6 4-10 0-16" />
        </g>
        <ellipse className="loader-dough" cx="60" cy="47" rx="36" ry="15" />
        <path className="loader-bowl-shape" d="M14 50h92c0 22-20 36-46 36S14 72 14 50z" />
        <path className="loader-bowl-rim" d="M10 50h100" />
      </svg>
      <p className="loader-step" aria-hidden="true" key={step}>
        {STEPS[step]}
      </p>
      <p className="visually-hidden" role="status">
        Finding an answer. This usually takes a few seconds.
      </p>
    </div>
  );
}
