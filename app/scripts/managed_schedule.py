"""夕方の便り係(Managed Agents)の定期実行を確かめる・止める・再開する。

python app/scripts/managed_schedule.py status     # 状態と、最近の実行(手動 / 定期)
python app/scripts/managed_schedule.py pause      # 毎日 18:00 の実行を止める(手動実行はできる)
python app/scripts/managed_schedule.py unpause    # 次の 18:00 から再開する(止めていたあいだの分は走らない)

定期実行は 1 回ごとに費用がかかる(上限 $0.50 / 回。deployment-evening.yaml の budget)。試し終わったら pause する。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fusuma.brain import llm, managed  # noqa: E402


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    cl = llm.client()
    dep_id = managed.ids()["deployment-evening"]
    if cmd == "pause":
        cl.beta.deployments.pause(dep_id)
    elif cmd == "unpause":
        cl.beta.deployments.unpause(dep_id)
    elif cmd != "status":
        sys.exit(__doc__)
    dep = cl.beta.deployments.retrieve(dep_id)
    print(f"deployment {dep_id}: {dep.status}" + (f" ({dep.paused_reason.type})" if getattr(dep, "paused_reason", None) else ""))
    for run in list(cl.beta.deployment_runs.list(deployment_id=dep_id))[:8]:
        kind = getattr(run.trigger_context, "type", "?")
        print(f"  {run.created_at.astimezone(managed.JST):%m-%d %H:%M} {kind:8} {run.session_id or run.error.type}")


if __name__ == "__main__":
    main()
