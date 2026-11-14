import {
  DEFAULT_ANSWER_STYLE,
  type AnswerStyle,
} from "../types/api";

type Option<T extends string> = { value: T; label: string };

const LEVELS: Option<AnswerStyle["level"]>[] = [
  { value: "beginner", label: "Beginner" },
  { value: "expert", label: "Expert" },
];

const LENGTHS: Option<AnswerStyle["length"]>[] = [
  { value: "short", label: "Short" },
  { value: "medium", label: "Medium" },
  { value: "long", label: "Detailed" },
];

const TONES: Option<AnswerStyle["tone"]>[] = [
  { value: "friendly", label: "Friendly" },
  { value: "professional", label: "Professional" },
  { value: "technical", label: "Technical" },
];

/** Plain-language description of a style, e.g. "beginner · friendly · medium length". */
export function describeStyle(style: AnswerStyle): string {
  const length =
    LENGTHS.find((option) => option.value === style.length)?.label ?? "";
  const tone = TONES.find((option) => option.value === style.tone)?.label ?? "";
  const reader = style.eli12 ? "explained like you’re 12" : `for ${style.level === "expert" ? "an expert" : "a beginner"}`;
  return `${reader} · ${tone.toLowerCase()} · ${length.toLowerCase()}`;
}

function isDefault(style: AnswerStyle): boolean {
  return (Object.keys(DEFAULT_ANSWER_STYLE) as (keyof AnswerStyle)[]).every(
    (key) => style[key] === DEFAULT_ANSWER_STYLE[key],
  );
}

type ChoiceGroupProps<T extends string> = {
  name: string;
  legend: string;
  options: Option<T>[];
  value: T;
  disabled?: boolean;
  onChange: (value: T) => void;
};

function ChoiceGroup<T extends string>({
  name,
  legend,
  options,
  value,
  disabled = false,
  onChange,
}: ChoiceGroupProps<T>) {
  return (
    <fieldset className="style-choice" disabled={disabled}>
      <legend>{legend}</legend>
      <div className="style-segments">
        {options.map((option) => (
          <label
            key={option.value}
            className={option.value === value ? "selected" : ""}
          >
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={option.value === value}
              onChange={() => onChange(option.value)}
            />
            {option.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

type AnswerStyleControlsProps = {
  style: AnswerStyle;
  onChange: (change: Partial<AnswerStyle>) => void;
  onReset: () => void;
};

/** Lets the reader choose how answers are written; facts and sources never change. */
export function AnswerStyleControls({
  style,
  onChange,
  onReset,
}: AnswerStyleControlsProps) {
  return (
    <details className="answer-style">
      <summary>
        <span className="answer-style-label">Answer style:</span>{" "}
        {describeStyle(style)}
      </summary>
      <div className="answer-style-body">
        <p className="answer-style-help">
          Changes how the answer is written, not what it says: it still uses
          only your documents and shows its sources.
        </p>

        <label className="style-eli12">
          <input
            type="checkbox"
            checked={style.eli12}
            onChange={(event) => onChange({ eli12: event.target.checked })}
          />
          Explain it like I’m 12
        </label>

        <ChoiceGroup
          name="answer-level"
          legend="Reading level"
          options={LEVELS}
          value={style.eli12 ? "beginner" : style.level}
          disabled={style.eli12}
          onChange={(level) => onChange({ level })}
        />
        {style.eli12 && (
          <p className="style-note">
            “Explain it like I’m 12” already uses simple words, so the reading
            level is set to Beginner.
          </p>
        )}

        <ChoiceGroup
          name="answer-length"
          legend="Length"
          options={LENGTHS}
          value={style.length}
          onChange={(length) => onChange({ length })}
        />

        <ChoiceGroup
          name="answer-tone"
          legend="Tone"
          options={TONES}
          value={style.tone}
          onChange={(tone) => onChange({ tone })}
        />

        {!isDefault(style) && (
          <button type="button" className="style-reset" onClick={onReset}>
            Back to the default style
          </button>
        )}
      </div>
    </details>
  );
}
