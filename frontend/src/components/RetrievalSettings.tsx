import type { ChangeEvent } from "react";
import "../../styles/retrieval-settings.css";

type RetrievalSettingsValues = {
  chunk_size: string;
  overlap: string;
  top_k: string;
};

type RetrievalSettingsProps = {
  settings: RetrievalSettingsValues;
  updateSetting: (field: keyof RetrievalSettingsValues, value: string) => void;
  saveSettings: () => Promise<void>;
  isSaving: boolean;
  message: string;
  hasError: boolean;
};

export function RetrievalSettings({
  settings,
  updateSetting,
  saveSettings,
  isSaving,
  message,
  hasError,
}: RetrievalSettingsProps) {
  function handleChange(
    field: keyof RetrievalSettingsValues,
    event: ChangeEvent<HTMLInputElement>,
  ) {
    updateSetting(field, event.target.value);
  }

  return (
    <section
      className="retrieval-settings"
      aria-labelledby="retrieval-settings-title"
    >
      <div className="section-heading">
        <span className="section-icon" aria-hidden="true">
          ⚙
        </span>
        <div>
          <h2 id="retrieval-settings-title">Search settings</h2>
          <p>Fine-tune the chunks the app pulls back for each question.</p>
        </div>
      </div>

      <div className="settings-grid">
        <label>
          Chunk size
          <input
            type="number"
            min="100"
            max="2000"
            value={settings.chunk_size}
            onChange={(event) => handleChange("chunk_size", event)}
          />
        </label>
        <label>
          Overlap
          <input
            type="number"
            min="0"
            max="1000"
            value={settings.overlap}
            onChange={(event) => handleChange("overlap", event)}
          />
        </label>
        <label>
          Top-k
          <input
            type="number"
            min="1"
            max="20"
            value={settings.top_k}
            onChange={(event) => handleChange("top_k", event)}
          />
        </label>
      </div>

      <div className="settings-actions">
        <button
          type="button"
          className="button secondary"
          onClick={() => void saveSettings()}
          disabled={isSaving}
        >
          {isSaving ? "Saving..." : "Apply settings"}
        </button>
        {message && (
          <p
            className={hasError ? "settings-message error" : "settings-message"}
            role="status"
          >
            {message}
          </p>
        )}
      </div>
    </section>
  );
}
