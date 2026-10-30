import { useEffect, useState } from "react";
import { getConfig, type SiteConfig } from "./api";

const DEFAULT_CONFIG: SiteConfig = { accessCodeRequired: false, aiExplanations: false };

/** Asks the server once how the site is set up. Until it answers, no code is asked for. */
export function useSiteConfig(): SiteConfig {
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  useEffect(() => {
    let cancelled = false;
    void getConfig().then((answer) => {
      if (!cancelled) setConfig(answer);
    });
    return () => {
      cancelled = true;
    };
  }, []);
  return config;
}
