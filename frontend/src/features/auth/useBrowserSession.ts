import { useEffect, useState } from "react";
import { readDemoSession, restoreBrowserSession, sessionExpired, rejectUnauthenticatedBrowserSession } from "../tasks/sessionCache";
import type { DemoSession } from "../tasks/api";

/** Identity pages wait for the Cookie-backed check, even when a local cache
 * exists. A failed check never falls back to an anonymous demo workspace. */
export function useBrowserSession(identityPilot: boolean) {
  const [session, setSession] = useState<DemoSession | null>(() => identityPilot ? null : readDemoSession());
  const [checking, setChecking] = useState(identityPilot);
  const [needsLogin, setNeedsLogin] = useState(false);
  const [recoveryError, setRecoveryError] = useState<unknown>(null);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!identityPilot) return;
    let active = true;
    const controller = new AbortController();
    setSession(null); setChecking(true); setNeedsLogin(false); setRecoveryError(null);
    restoreBrowserSession(controller.signal).then(value => {
      if (active) setSession(value);
    }).catch(error => {
      if (active) { setNeedsLogin(sessionExpired(error)); setRecoveryError(error); }
    }).finally(() => { if (active) setChecking(false); });
    return () => { active = false; controller.abort(); };
  }, [identityPilot, retry]);
  function rejectExpiredSession(error: unknown) {
    if (!identityPilot || !rejectUnauthenticatedBrowserSession(error)) return;
    setSession(null); setNeedsLogin(true); setRecoveryError(error);
  }
  return { session, setSession, checking, needsLogin, recoveryError, rejectExpiredSession,
    retryRecovery: () => setRetry(value => value + 1) };
}
