/**
 * Readable names for document IDs, which are file paths such as
 * "bread/bread_not_rising.md". The path stays the ID (and the tooltip);
 * people see "Bread not rising" with the folder "Bread" as a category.
 */

function humanise(part: string): string {
  const words = part.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : part;
}

/** "bread/bread_not_rising.md" → "Bread not rising". */
export function documentTitle(path: string): string {
  const fileName = path.split("/").pop() ?? path;
  return humanise(fileName.replace(/\.(md|txt)$/i, ""));
}

/** "bread/bread_not_rising.md" → "Bread"; a top-level file has no category. */
export function documentCategory(path: string): string | null {
  const parts = path.split("/");
  return parts.length > 1 ? humanise(parts[parts.length - 2]) : null;
}
