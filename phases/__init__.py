import sys
import traceback

def _import_phase(name):
    try:
        module = __import__(f"phases.{name}", fromlist=["apply"])
        return module.apply
    except Exception as e:
        print(f"ERROR importing {name}: {e}")
        traceback.print_exc()
        sys.exit(1)

phase_01 = _import_phase("phase_01_apply_queued")
phase_02 = _import_phase("phase_02_gather")
phase_03 = _import_phase("phase_03_refining")
phase_04 = _import_phase("phase_04_trade")
phase_05 = _import_phase("phase_05_research")
phase_06 = _import_phase("phase_06_build")
phase_07 = _import_phase("phase_07_maintain")
phase_08 = _import_phase("phase_08_produce")
phase_09 = _import_phase("phase_09_policy_stability")
phase_10 = _import_phase("phase_10_commit")