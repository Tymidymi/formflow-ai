/* Bound simultaneous conversion requests while keeping all selected files queued.
 * Individual failures cannot prevent subsequent files from starting.
 */
(function (root) {
  "use strict";
  const MAX_FILES = 10;
  const MAX_PARALLEL = 3;

  async function processAll(items, task, limit = MAX_PARALLEL) {
    if (!Array.isArray(items) || items.length < 1 || items.length > MAX_FILES)
      throw Error("Liczba dokumentów musi wynosić od 1 do 10.");
    if (typeof task !== "function") throw TypeError("Task must be callable.");
    const workers = Math.min(items.length, Math.max(1, Math.min(MAX_PARALLEL, Math.floor(Number(limit) || 1))));
    const outcomes = Array(items.length);
    let cursor = 0;
    async function consume() {
      while (cursor < items.length) {
        const index = cursor++;
        try {
          outcomes[index] = { ok: true, value: await task(items[index], index) };
        } catch (error) {
          outcomes[index] = { ok: false, error };
        }
      }
    }
    await Promise.all(Array.from({ length: workers }, consume));
    return outcomes;
  }
  root.FormFlowBatchRunner = Object.freeze({ MAX_FILES, MAX_PARALLEL, processAll });
})(window);
