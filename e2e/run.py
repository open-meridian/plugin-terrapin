"""`make e2e`: the plugin on the plugin harness of the runtime it pins
(contract v29), beside `reader`, a reporting plugin (e2e/reader.py) entitled
to its datasets, and the harness's admin. Run from the repository's root by
the Makefile, which builds the image and writes the harness's plugins first;
standard library only. The harness's stand-in for the platform mints a
corporate bond by its FIGI (BBG01BOND0001) and knows Apple Inc.'s LEI.

No Terrapin key is used: Terrapin's API answers nowhere (the e2e's hosts
file), and sample data answers from the answers committed with the plugin,
made in the shape of Terrapin's public documentation.

1. No key: Connection says "No key", and nothing is recorded.
2. Sample data on, two securities listed -- the sample corporate, whose
   FIGI the harness's platform mints from, and the sample municipal bond --
   both resolved.
3. Parity: through the deployment's MCP, `read_connection` answers what the
   page shows -- the corporate's platform record, its issuer's `ENT-` by
   its LEI, its terms offered; the municipal bond a record, no LEI stated --
   and `read_datasets` the three datasets and the US curve's record; core's
   `dashboard__list_datasets` lists the three as the catalogue declares them.
4. The lake holds the sample week's par curves (three regions, five days,
   ten tenors but the US curve's 25-year on 29 October), 36 inflation index
   levels and the municipal bond's four prints, one kept with what does not
   convert, and no price.
5. Licensed and entitled, the reader reads the US par curve of 30 October:
   ten points in tenor order, the 10-year 4.109 per cent, a par yield,
   bond-equivalent.
6. Declined: the corporate's record asked of the curves, which it is not.
"""

import json
import os
import subprocess
import sys
import time

PROJECT = "terrapin-e2e"
LOG = ".e2e/runner.log"
COMPONENTS = ".e2e/components.log"
COMPOSE = ["docker", "compose", "-p", PROJECT, "-f", ".e2e/harness/compose.yaml",
           "-f", ".e2e/harness/plugins.yaml", "-f", "e2e/plugin.yaml"]
INSTANCE = "terrapin"
KEYS = ["government_curves", "inflation", "muni_trades"]
DATASETS = [f"{INSTANCE}:{key}" for key in KEYS]
CURVES, INFLATION, TRADES = DATASETS
APPLE, MUNI = "US037833ER75", "US005824LP01"
#: The harness platform's company record of Apple Inc., by its LEI.
APPLE_COMPANY = "ENT-01JC28APPLEINC000000000001"
DAY = "2026-10-30"


class Failed(Exception):
    pass


def log(text):
    with open(LOG, "a", encoding="utf-8") as kept:
        kept.write(text + "\n")


def compose(*args, check=True, timeout=600):
    done = subprocess.run(COMPOSE + list(args), capture_output=True, text=True,
                          timeout=timeout)
    log(f"$ compose {' '.join(args)[:300]}\n{done.stdout[-4000:]}{done.stderr[-2000:]}")
    if check and done.returncode != 0:
        raise Failed(f"compose {' '.join(args)[:200]}: {(done.stdout + done.stderr).strip()[-600:]}")
    return done


def runner(*args, check=True):
    done = compose("run", "--rm", "-T", "runner", *args, check=check)
    return done.stdout if check else done


def must(condition, why):
    if not condition:
        raise Failed(why)


def until(seconds, attempt, what):
    deadline = time.monotonic() + seconds
    last = None
    while True:
        try:
            answer = attempt()
        except Failed as failed:
            answer, last = None, failed
        if answer:
            return answer
        if time.monotonic() > deadline:
            raise Failed(f"{what}, in {seconds} seconds" + (f": {last}" if last else ""))
        time.sleep(2)


def page(instance, level, path):
    said = runner("page", "--instance", instance, "--level", level, path)
    status, _, body = said.partition("\n")
    must(status.strip() == "200", f"{instance} {path} answered {said[-600:]}")
    return body


def call(tool, arguments=None):
    done = runner("mcp", "call", tool, json.dumps(arguments or {}), check=False)
    try:
        answer = json.loads(done.stdout)
    except ValueError:
        raise Failed(f"{tool}: no answer: {(done.stdout + done.stderr)[-400:]}")
    must(answer.get("outcome") in ("read", "unchanged"), f"{tool} answered {done.stdout[-700:]}")
    return answer["data"]


def store_lake():
    return compose("run", "--rm", "-T", "store", "lake").stdout


def reader(path):
    return json.loads(page("reader", "read", path))


def run():
    started = time.time()
    compose("--profile", "runner", "down", "-v", "--remove-orphans", check=False)
    compose("up", "-d")
    runner("ready")
    runner("ready", "--instance", "reader")

    # 1. No key.
    runner("page", "--level", "admin", "/", "--until", "No key", "--seconds", "90")
    lake = store_lake()
    must("row|" not in lake, f"step 1, nothing recorded without a key: {lake[-500:]}")

    # 2. Sample data, two securities listed.
    runner("settings", "sample_data=true", f"securities[0].security={APPLE}",
           f"securities[1].security={MUNI}")
    runner("page", "--level", "admin", "/", "--until", "2 of 2 resolved", "--seconds", "180")

    # 3. Parity through the deployment's MCP, and core's view of the catalogue.
    runner("grant", "--level", "admin", "--role", "data")
    runner("mcp", "connect", "--covers", "deployment_admin", "--covers", f"{INSTANCE}:data:admin")
    tools = runner("mcp", "list").split()
    read_connection = next((t for t in tools if t.endswith("read_connection")), "")
    read_datasets = next((t for t in tools if t.endswith("read_datasets")), "")
    must(read_connection and read_datasets, f"step 3, the plugin's two tools are listed: {tools}")
    connection = call(read_connection)
    held = {s["security"]: s for s in connection["securities"]}
    apple, muni = held.get(APPLE, {}), held.get(MUNI, {})
    must(connection["mode"] == "Sample data"
         and connection["credentials"] == [{"label": "Terrapin API key", "set": False}]
         and apple.get("record", "").startswith("INS-") and apple.get("issuer") == APPLE_COMPANY
         and apple.get("offered", 0) > 10
         and muni.get("record", "").startswith(("LCL-", "INS-"))
         and muni.get("issuer") == "no LEI stated",
         f"step 3, read_connection: {connection}")
    bond = apple["record"]
    datasets = call(read_datasets)
    records = {r["code"]: r["record"] for r in datasets["records"]}
    us_curve = records.get("TERRAPIN_US_PAR", "")
    must([s["dataset"] for s in datasets["served"]] == DATASETS and us_curve,
         f"step 3, read_datasets: {datasets}")
    shown = page(INSTANCE, "admin", "/datasets")
    must(us_curve in shown, "step 3, Datasets shows the curve's record read_datasets names")
    listed = {d["dataset"]: d for d in call("dashboard__list_datasets")["datasets"]}
    entry = listed.get(TRADES, {}).get("catalogue_entry", {})
    must(entry.get("modes") == ["push", "pull"] and entry.get("day_time_zone") == "America/New_York",
         f"step 3, core lists {TRADES} as declared: {listed.get(TRADES)}")
    must(all(d in listed for d in DATASETS), f"step 3, core lists the three datasets: {list(listed)}")

    # 4. The lake: the week's curves, the indexes and the prints; no price.
    def rows(dataset, kind):
        return [line for line in store_lake().splitlines()
                if line.startswith(f"row|{dataset}|{kind}|")]

    curves = until(120, lambda: (lambda r: r if len(r) == 149 else None)(rows(CURVES, "rate")),
                   "step 4, the week's par curves were not recorded")
    levels = rows(INFLATION, "rate")
    prints = rows(TRADES, "trade")
    must(len(levels) == 36, f"step 4, 36 inflation index levels: {len(levels)}")
    must(len(prints) == 4 and sum(1 for p in prints if not p.endswith("|")) == 1,
         f"step 4, four prints, one with what does not convert: {prints}")
    must(not any(line.startswith("row|") and "|price|" in line for line in store_lake().splitlines()),
         "step 4, no price recorded (ruling 900's R7)")
    must(all(f"|{us_curve}|" in line or "|LCL-" in line or "|INS-" in line for line in curves),
         "step 4, each point under a curve's record")

    # 5. Licensed and entitled: the US par curve of 30 October.
    runner("licence", CURVES, "kept=true", "retention_days=0", "derived_use=false",
           "display=true", "personal_use=false", "note=Terrapin's terms, as the deployment's agreement says.")
    runner("entitle", "--instance", "reader", CURVES, "note=The e2e's reader reads them.")
    runner("grant", "--instance", "reader", "--level", "read")
    curve = until(90, lambda: (lambda r: r if len(r["rates"]) == 10 else None)(
        reader(f"/curve?subject={us_curve}&date={DAY}&dataset={CURVES}")),
        "step 5, the US par curve of 30 October was not read")
    points = curve["rates"]
    ten = [r for r in points if r["tenor"] == "10Y"]
    must([r["tenor"] for r in points] == ["1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "15Y", "20Y", "25Y", "30Y"]
         and ten and ten[0]["value"] == "4.109" and ten[0]["kind"] == "RATE_KIND_PAR_YIELD"
         and ten[0]["unit"] == "VALUE_UNIT_PERCENT" and ten[0]["subject"] == us_curve
         and ten[0]["convention"] == ["DAY_COUNT_ACT_ACT", "COMPOUNDING_COMPOUNDED", 2]
         and ten[0]["business_date"] == DAY and ten[0]["dataset"] == CURVES,
         f"step 5, the curve in tenor order, the 10-year as Terrapin states it: {curve}")

    # 6. Declined: a bond is no curve.
    until(90, lambda: (lambda r: [u["reason"] for u in r["unanswered"]]
                       == ["UNANSWERED_REASON_NOT_COVERED"])(
        reader(f"/curve?subject={bond}&date={DAY}&dataset={CURVES}")),
        "step 6, the bond's curve was not declined not covered")
    lake = store_lake()
    must(f"want|{CURVES}|declined|{bond}|" in lake,
         f"step 6, the lake holds the decline: {[l for l in lake.splitlines() if l.startswith('want|')]}")

    print(f"e2e OK in {int(time.time() - started)}s on the plugin harness: no key said and nothing "
          f"recorded; sample data's two securities resolved, the corporate to the platform's "
          f"record with its issuer {APPLE_COMPANY} by LEI and its terms offered; "
          f"read_connection and read_datasets answering what the pages show, core listing the "
          f"three datasets as declared; 149 par points, 36 index levels and four prints in the "
          f"lake, no price; the US par curve of 30 October read in tenor order (10-year 4.109, "
          f"bond-equivalent); and a bond's curve declined not covered")


def main():
    os.makedirs(".e2e", exist_ok=True)
    open(LOG, "w").close()
    try:
        run()
    except (Failed, subprocess.TimeoutExpired, KeyError, ValueError, IndexError, TypeError) as failed:
        with open(COMPONENTS, "a", encoding="utf-8") as kept:
            kept.write(compose("logs", "--no-color", check=False).stdout)
        compose("--profile", "runner", "down", "-v", "--remove-orphans", check=False)
        print(f"e2e FAILED: {failed}; the runner's log is in {LOG}, the components' in {COMPONENTS}",
              file=sys.stderr)
        return 1
    compose("--profile", "runner", "down", "-v", "--remove-orphans", check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
