"""
Tier 2 — E2E Conversation Smoke Suite

Runs on the VM host (not inside the container). Drives real HTTP conversations
through the chatbot service, covering all major state-machine paths.

Created sessions and tickets are cleaned up afterwards via cleanup.sql using
the session IDs written to the output file. All complaint descriptions include
the marker '[benchmark]' for precise SQL cleanup.

Usage:
    python scripts/benchmark/e2e_smoke.py \
        --user-id <customer_uuid> \
        --base-url http://localhost:8001 \
        --output scripts/benchmark/e2e_MODEL.json \
        [--timeout 180]

Requirements:
    - chatbot service must be running and healthy on --base-url
    - --user-id must be a valid user UUID from the users table
    - Python >= 3.8, stdlib only (http.client, json, urllib)
"""

import argparse
import http.client
import json
import logging
import sys
import time
import urllib.parse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger(__name__)

BENCHMARK_MARKER = "[benchmark]"



# HTTP helpers


def _parse_base_url(base_url: str):
    """Return (host, port, is_https) from a base URL like http://localhost:8001."""
    parsed = urllib.parse.urlparse(base_url)
    host = parsed.hostname or "localhost"
    is_https = parsed.scheme == "https"
    port = parsed.port or (443 if is_https else 80)
    return host, port, is_https


def _make_conn(host: str, port: int, is_https: bool, timeout: int):
    if is_https:
        import ssl
        ctx = ssl.create_default_context()
        return http.client.HTTPSConnection(host, port, context=ctx, timeout=timeout)
    return http.client.HTTPConnection(host, port, timeout=timeout)


def _post_chat(host: str, port: int, is_https: bool, timeout: int, payload: dict) -> tuple[int, dict]:
    """POST /api/chat and return (status_code, response_json)."""
    body = json.dumps(payload).encode("utf-8")
    conn = _make_conn(host, port, is_https, timeout)
    try:
        conn.request(
            "POST",
            "/api/chat",
            body=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        resp = conn.getresponse()
        status = resp.status
        raw = resp.read().decode("utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"raw": raw}
        return status, data
    finally:
        conn.close()


def _get_health(host: str, port: int, is_https: bool, timeout: int) -> dict:
    conn = _make_conn(host, port, is_https, timeout)
    try:
        conn.request("GET", "/health", headers={"Accept": "application/json"})
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8")
        return {"status_code": resp.status, "body": json.loads(raw)}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Conversation driver
# ---------------------------------------------------------------------------

class ConversationDriver:
    def __init__(self, user_id: str, host: str, port: int, is_https: bool, timeout: int):
        self.user_id = user_id
        self.host = host
        self.port = port
        self.is_https = is_https
        self.timeout = timeout
        self.session_id = None
        self.turns: list[dict] = []

    def send(self, message: str | None = None) -> dict:
        """Send one message. Returns the parsed response dict."""
        payload = {"user_id": self.user_id, "session_id": self.session_id}
        if message is not None:
            payload["message"] = message

        t0 = time.perf_counter()
        status, data = _post_chat(
            self.host, self.port, self.is_https, self.timeout, payload
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

        turn = {
            "message": message,
            "status_code": status,
            "response": data.get("response", ""),
            "response_type": data.get("response_type", ""),
            "show_buttons": data.get("show_buttons", []),
            "elapsed_ms": elapsed_ms,
            "error": None if status < 400 else data,
        }
        self.turns.append(turn)

        if status < 400:
            self.session_id = data.get("session_id", self.session_id)
        elif 400 <= status < 500:
            log.warning("4xx on turn %d: %s %s", len(self.turns), status, data)
        else:
            log.error("5xx on turn %d: %s %s", len(self.turns), status, data)

        log.debug("  [%d] → type=%s  status=%d  %.0fms",
                  len(self.turns), turn["response_type"], status, elapsed_ms)
        return turn

    def init_session(self) -> dict:
        """Start a new session (greeting turn)."""
        return self.send(None)


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

def _scenario(sid: int, name: str, fn, driver: ConversationDriver) -> dict:
    log.info("Scenario %02d: %s", sid, name)
    t0 = time.perf_counter()
    success = True
    error_msg = None
    try:
        fn(driver)
        last_status = driver.turns[-1]["status_code"] if driver.turns else 0
        if last_status >= 500:
            success = False
            error_msg = f"Last turn returned HTTP {last_status}"
    except Exception as exc:
        success = False
        error_msg = str(exc)
        log.error("Scenario %02d failed: %s", sid, exc)

    elapsed = round(time.perf_counter() - t0, 2)
    log.info("Scenario %02d: %s  (%.1fs)  session=%s",
             sid, "PASS" if success else "FAIL", elapsed, driver.session_id)
    return {
        "scenario_id": sid,
        "name": name,
        "session_id": driver.session_id,
        "turns": driver.turns,
        "success": success,
        "error": error_msg,
        "duration_s": elapsed,
    }


def build_scenarios(user_id: str, host: str, port: int, is_https: bool, timeout: int) -> list:
    """Return a list of (scenario_id, name, fn) tuples."""

    def new_driver():
        return ConversationDriver(user_id, host, port, is_https, timeout)

    scenarios = []

    # ── 01: Follow-up with fake ticket ID ────────────────────────────────────
    def s01(d: ConversationDriver):
        d.init_session()
        d.send("I would like to follow up on my existing ticket")
        d.send("CX-FAKEID0001")

    scenarios.append((1, "follow_up_fake_ticket_id", s01, new_driver()))

    # ── 02: Inquiry confirmed resolved ───────────────────────────────────────
    def s02(d: ConversationDriver):
        d.init_session()
        d.send("I have a question about building access")
        d.send("How do I request a temporary visitor badge?")
        d.send("Yes that answered my question")

    scenarios.append((2, "inquiry_confirmed_resolved", s02, new_driver()))

    # ── 03: Inquiry not resolved → second attempt → resolved ─────────────────
    def s03(d: ConversationDriver):
        d.init_session()
        d.send("I need some information")
        d.send("What is the procedure for booking a meeting room?")
        d.send("No, I need more detail about booking for external guests")
        d.send("Yes, thank you that is helpful")

    scenarios.append((3, "inquiry_second_attempt_resolved", s03, new_driver()))

    # ── 04: Complaint → Office → ticket created ───────────────────────────────
    def s04(d: ConversationDriver):
        d.init_session()
        d.send("I want to report a problem")
        d.send("The lights in our section have not been working for two days")
        d.send("Office")
        d.send(f"Lighting failure on floor 2, eastern wing. Urgent repair needed. {BENCHMARK_MARKER}")

    scenarios.append((4, "complaint_office_ticket_created", s04, new_driver()))

    # ── 05: Complaint → Warehouse → ticket created ────────────────────────────
    def s05(d: ConversationDriver):
        d.init_session()
        d.send("I need to raise a complaint")
        d.send("The loading bay door is stuck and cannot be closed")
        d.send("Warehouse")
        d.send(f"Loading bay door mechanism failure, security risk. {BENCHMARK_MARKER}")

    scenarios.append((5, "complaint_warehouse_ticket_created", s05, new_driver()))

    # ── 06: Complaint → Retail → ticket created ───────────────────────────────
    def s06(d: ConversationDriver):
        d.init_session()
        d.send("I have a maintenance issue to report")
        d.send("The air conditioning unit in the retail area has been broken for three days")
        d.send("Retail")
        d.send(f"AC unit failure in retail floor. Staff and customers affected. {BENCHMARK_MARKER}")

    scenarios.append((6, "complaint_retail_ticket_created", s06, new_driver()))

    # ── 07: Aggression mid-flow (state = await_secondary_intent) ─────────────
    def s07(d: ConversationDriver):
        d.init_session()
        d.send("I need to report something")
        # Now in await_secondary_intent — aggression check is active
        d.send("This is absolutely unacceptable and I am furious, sort this out RIGHT NOW")

    scenarios.append((7, "aggression_in_secondary_intent_state", s07, new_driver()))

    # ── 08: Unknown primary intent → re-prompt → create ticket → resolved ────
    def s08(d: ConversationDriver):
        d.init_session()
        d.send("Hello")
        # Unknown → re-prompt, still in await_primary_intent
        d.send("I need to submit a new issue")
        d.send("How do I access the staff car park after hours?")
        d.send("Yes that helps, thank you")

    scenarios.append((8, "unknown_then_inquiry_resolved", s08, new_driver()))

    # ── 09: Follow-up with CX- ticket code format ─────────────────────────────
    def s09(d: ConversationDriver):
        d.init_session()
        d.send("Track my ticket")
        d.send("CX-AA11BB22")

    scenarios.append((9, "follow_up_cx_code_format", s09, new_driver()))

    # ── 10: Complaint → asset type re-prompt → ticket created ─────────────────
    def s10(d: ConversationDriver):
        d.init_session()
        d.send("I want to make a complaint")
        d.send("There is a burst pipe leaking water")
        d.send("I am not sure which category")     # asset type not detected
        d.send("Office")                            # correct asset type
        d.send(f"Burst pipe in office bathroom, water on floor, slip hazard. {BENCHMARK_MARKER}")

    scenarios.append((10, "complaint_asset_type_reprompt_then_created", s10, new_driver()))

    # ── 11: Multi-turn: inquiry → resolved → then follow-up ──────────────────
    def s11(d: ConversationDriver):
        d.init_session()
        d.send("I have a question")
        d.send("What are the fire evacuation procedures?")
        d.send("Yes that answered my question")
        # Session continues, user asks something else
        d.send("I want to check on a ticket I submitted")
        d.send("CX-NONE0000")

    scenarios.append((11, "inquiry_resolved_then_follow_up", s11, new_driver()))

    # ── 12: Long text inquiry (stress test, ~600 chars) ──────────────────────
    def s12(d: ConversationDriver):
        long_text = (
            "I have a very detailed question about the building maintenance policy. "
            "Specifically I am trying to understand the escalation process when a "
            "maintenance request has been open for more than 14 days with no update. "
            "The policy document I received says requests are resolved within 5 working days "
            "for standard issues and 24 hours for safety-related issues, but I cannot find "
            "any information about what happens when these deadlines are missed. Is there an "
            "escalation path I can use? Who do I contact? Is there a formal complaints process "
            "beyond the ticketing system? I would appreciate a clear and detailed answer."
        )
        d.init_session()
        d.send("I need some information about building policies")
        d.send(long_text)
        d.send("Yes, that was helpful thank you")

    scenarios.append((12, "inquiry_long_text_stress_test", s12, new_driver()))

    # ── 13: Aggressive opening message (await_primary_intent, no agg check) ──
    def s13(d: ConversationDriver):
        # Aggression check is SKIPPED in await_primary_intent per controller logic.
        # This tests whether the LLM can still classify intent from an aggressive message.
        d.init_session()
        d.send("Your system is a JOKE. I need to log a complaint right now")
        d.send("The server room AC failed and it is critical")
        d.send("Office")
        d.send(f"Server room AC failure, temperature critical, equipment at risk. {BENCHMARK_MARKER}")

    scenarios.append((13, "aggressive_first_message_complaint_flow", s13, new_driver()))

    # ── 14: Aggression in complaint collecting state ───────────────────────────
    def s14(d: ConversationDriver):
        d.init_session()
        d.send("Report a problem with the building")
        d.send("The roof has been leaking for two months")
        d.send("Office")
        # Now in collecting_complaint, waiting for description — send aggressive msg
        d.send("You people are completely useless, why has nothing been done, I am going to HR")

    scenarios.append((14, "aggression_in_collecting_complaint_state", s14, new_driver()))

    # ── 15: Health check round-trip (sanity baseline) ─────────────────────────
    def s15(d: ConversationDriver):
        d.init_session()
        d.send("Hello I need help")
        d.send("I need to create a new support request")

    scenarios.append((15, "sanity_baseline_init_and_create", s15, new_driver()))

    return scenarios


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="E2E chatbot smoke test suite")
    parser.add_argument("--user-id", required=True, help="Valid user UUID from the DB")
    parser.add_argument("--base-url", default="http://localhost:8001",
                        help="Chatbot service base URL (default: http://localhost:8001)")
    parser.add_argument("--output", required=True, help="Path to write results JSON")
    parser.add_argument("--timeout", type=int, default=180,
                        help="HTTP timeout per request in seconds (default: 180)")
    args = parser.parse_args()

    host, port, is_https = _parse_base_url(args.base_url)
    log.info("Target: %s:%d  user_id=%s  timeout=%ds",
             host, port, args.user_id, args.timeout)

    # ── Health check ─────────────────────────────────────────────────────────
    log.info("Checking service health ...")
    try:
        health = _get_health(host, port, is_https, 10)
        if health["status_code"] != 200:
            log.error("Health check failed: %s", health)
            sys.exit(1)
        log.info("Health OK: %s", json.dumps(health["body"]))
        if health["body"].get("chatbot_mode") == "mock":
            log.warning(
                "Service is in MOCK mode. E2E responses will be deterministic mock outputs, "
                "not real LLM responses. Results will be identical for both models."
            )
    except Exception as exc:
        log.error("Cannot reach chatbot service at %s:%d — %s", host, port, exc)
        sys.exit(1)

    # ── Build and run scenarios ───────────────────────────────────────────────
    scenarios_spec = build_scenarios(args.user_id, host, port, is_https, args.timeout)
    results = []
    session_ids = []

    total = len(scenarios_spec)
    for sid, name, fn, driver in scenarios_spec:
        result = _scenario(sid, name, fn, driver)
        results.append(result)
        if result["session_id"]:
            session_ids.append(result["session_id"])

    # ── Summary ──────────────────────────────────────────────────────────────
    passed = sum(1 for r in results if r["success"])
    failed = total - passed
    total_turns = sum(len(r["turns"]) for r in results)
    total_duration = sum(r["duration_s"] for r in results)
    avg_duration = round(total_duration / total, 2) if total else 0

    print("\n=== E2E SMOKE SUITE SUMMARY ===")
    print(f"Total scenarios : {total}")
    print(f"Passed          : {passed}")
    print(f"Failed          : {failed}")
    print(f"Total turns     : {total_turns}")
    print(f"Total time      : {total_duration:.1f}s")
    print(f"Avg per scenario: {avg_duration}s\n")

    for r in results:
        status = "PASS" if r["success"] else "FAIL"
        err = f"  [{r['error']}]" if r["error"] else ""
        print(f"  [{status}] {r['scenario_id']:02d}. {r['name']:<45} {r['duration_s']:6.1f}s{err}")
    print()

    if failed:
        print("Failed scenarios:")
        for r in results:
            if not r["success"]:
                print(f"  - {r['scenario_id']:02d}. {r['name']}: {r['error']}")
    print()

    # ── Write output ──────────────────────────────────────────────────────────
    output = {
        "meta": {
            "base_url": args.base_url,
            "user_id": args.user_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "timeout_s": args.timeout,
            "total_scenarios": total,
            "passed": passed,
            "failed": failed,
            "total_turns": total_turns,
            "total_duration_s": round(total_duration, 2),
        },
        "session_ids": list(set(session_ids)),
        "scenarios": results,
        "summary": {
            "completion_rate_pct": round(passed / total * 100, 1) if total else 0,
            "avg_scenario_duration_s": avg_duration,
        },
    }

    import os
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)
    log.info("Results written to %s", args.output)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
