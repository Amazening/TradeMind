import { useEffect, useState } from "react";
import { getConfig } from "./api";

/** Asks the server once whether the site is invite-only. Until it answers, no code is asked for. */
export function useAccessCodeRequired(): boolean {
  const [required, setRequired] = useState(false);
  useEffect(() => {
    let cancelled = false;
    void getConfig().then((config) => {
      if (!cancelled) setRequired(config.accessCodeRequired);
    });
    return () => {
      cancelled = true;
    };
  }, []);
  return required;
}
