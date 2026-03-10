/**
 * Tiny event bus for triggering an immediate notification refresh
 * after any action that creates a notification (resolve, approve,
 * rescore, reroute, etc.).
 *
 * Usage — fire from any action handler after a successful API call:
 *   import { fireNotifRefresh } from "../utils/notifRefresh";
 *   fireNotifRefresh();
 *
 * The hooks (useUnreadCount, usePendingApprovals) listen for this
 * event and re-fetch immediately instead of waiting for the next
 * 60-second poll cycle.
 */

const NOTIF_REFRESH_EVENT = "notif-refresh";

/** Fire from action handlers after a successful mutation. */
export function fireNotifRefresh() {
  window.dispatchEvent(new CustomEvent(NOTIF_REFRESH_EVENT));
}

/** Subscribe to refresh events. Returns an unsubscribe function. */
export function onNotifRefresh(handler) {
  window.addEventListener(NOTIF_REFRESH_EVENT, handler);
  return () => window.removeEventListener(NOTIF_REFRESH_EVENT, handler);
}
