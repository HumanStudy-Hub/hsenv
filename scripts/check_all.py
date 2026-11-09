"""Run hsenv.checks over every study (or the named ones) and write studies/<id>/review/checks-latest.json.

    /usr/local/bin/python3 scripts/check_all.py [study ...] [-j N]

Studies run in parallel (-j, default 6; slow studies start first) and print one line each as they finish."""
import glob, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.version_info < (3, 11):   # coding rules use regex features of Python 3.11+ (atomic groups); LESSONS 286
    sys.exit("check_all needs Python 3.11+ (found %s); try /usr/local/bin/python3" % sys.version.split()[0])
from hsenv.checks import PRIVATE   # study-specific settings live in the private config, never in this script
PY = sys.executable
FETCH_PREFIXES = tuple(PRIVATE.get("fetch_images_study_prefixes") or ())


def run(st):
    d = "studies/%s/" % st
    args = [PY, "-m", "hsenv.checks", "studies/" + st, "--sessions", "1000"]
    for f in sorted(glob.glob(d + "sourcetext/*.txt")):
        args += ["--source-text", "%s=%s" % (os.path.basename(f)[:-4], f)]
    proto = open(d + "protocol.json").read()
    if (FETCH_PREFIXES and st.startswith(FETCH_PREFIXES)) or '"src": "http' in proto or '"src":"http' in proto:
        args.append("--fetch-images")   # any study serving remote images is image-checked (skills README open 9)
    p = subprocess.run(args, capture_output=True, text=True)
    os.makedirs(d + "review", exist_ok=True)
    open(d + "review/checks-latest.json", "w").write(p.stdout)
    try:
        r = json.loads(p.stdout)
    except Exception:
        return "%-26s CRASH %s" % (st, (p.stderr.strip().splitlines() or [""])[-1][:200])
    f, v = r["fuzz"], r["verbatim"]
    return ("%-26s PASS=%s refs=%d leaks=%d unreached=%d problems=%d nc=%d verbatim=%d nf=%d unconf=%d coding=%s "
            "hold=%d foreign=%d constimg=%s pending=%s exprleak=%d ann=%s" % (
                st, r["PASS"], len(r["refs"]), len(f["leaks"]), len(f["unreached_stages"]), len(f["problems"]),
                len(f["effects_not_computed"]), v["found"], len(v["not_found"]), len(v["image_unconfirmed"]),
                {k: x["n_mismatches"] for k, x in r.get("coding", {}).items()}, len(r.get("release_hold", [])),
                len(f.get("foreign_language_tokens", [])), f.get("constant_images", []),
                max(f.get("pending_share", {}).values() or [0]), f.get("n_state_expr_leaks", 0) +
                len((r.get("keyed") or {}).get("state_expr_leaks") or []),
                [(x.get("source"), x.get("lines_changed", x.get("error"))) for x in r.get("reading_annotations", [])]))


def main(argv):
    jobs = 6
    if "-j" in argv:
        k = argv.index("-j")
        jobs = int(argv[k + 1])
        argv = argv[:k] + argv[k + 2:]
    studies = [os.path.basename(d.rstrip("/")) for d in sorted(glob.glob("studies/*/"))
               if os.path.isfile(d + "protocol.json") and (not argv or os.path.basename(d.rstrip("/")) in argv)]
    # the biggest protocols first, so the slow ones do not finish last alone
    studies.sort(key=lambda s: -os.path.getsize("studies/%s/protocol.json" % s))
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        futs = {ex.submit(run, st): st for st in studies}
        for fut in as_completed(futs):
            try:
                print(fut.result())
            except Exception as e:   # one study's failure never stops the others
                print("%-26s CRASH %s" % (futs[fut], e))
            sys.stdout.flush()


if __name__ == "__main__":
    main(sys.argv[1:])
