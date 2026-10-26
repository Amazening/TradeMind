import { useEffect, useRef } from "react";

/**
 * Moves keyboard and screen reader focus to a heading when a screen appears. Turn it off for the
 * first screen, so a keyboard user can still reach the skip link when the page loads.
 */
export function useFocusOnMount<T extends HTMLElement>(enabled = true) {
  const ref = useRef<T>(null);
  useEffect(() => {
    if (enabled) ref.current?.focus();
  }, [enabled]);
  return ref;
}
