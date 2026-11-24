from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import re
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import itasca


SCHEMA_VERSION = 1
DATA_BOUNDARY = "REAL_PFC"
CAPTURE_CALLBACK = "_pfc_live_capture_cycle"
CAPTURE_FRAME = "_pfc_live_capture_frame"
CAPTURE_BOND = "_pfc_live_capture_bond"
CAPTURE_POSITION = 49.5


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def fish_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace("'", "\\'")


def vector3(value: Any) -> list[float]:
    result = [float(item) for item in list(value)]
    if len(result) == 2:
        result.append(0.0)
    if len(result) != 3 or not all(math.isfinite(item) for item in result):
        raise RuntimeError(f"Invalid 2D/3D vector from PFC: {value!r}")
    return result


def snapshot() -> dict[str, Any]:
    fracture_count = None
    if hasattr(itasca, "dfn"):
        fracture_count = int(itasca.dfn.fracture.count())
    return {
        "pid": int(os.getpid()),
        "cwd": str(Path.cwd()),
        "python": platform.python_version(),
        "cycle": int(itasca.cycle()),
        "mechanical_time_total": float(itasca.mech_age()),
        "balls": int(itasca.ball.count()),
        "walls": int(itasca.wall.count()),
        "contacts": int(itasca.contact.count()),
        "fractures": fracture_count,
        "fracture_module_available": fracture_count is not None,
    }


def read_ball_static() -> dict[str, Any]:
    records = []
    for ball in itasca.ball.list():
        pos = vector3(ball.pos())
        records.append(
            {
                "id": int(ball.id()),
                "x": float(pos[0]),
                "y": float(pos[1]),
                "z": float(pos[2]),
                "radius": float(ball.radius()),
            }
        )
    records.sort(key=lambda row: row["id"])
    return {
        "count": len(records),
        "ids": [row["id"] for row in records],
        "balls": records,
    }


def read_wall_static() -> dict[str, Any]:
    walls = []
    for wall in itasca.wall.list():
        walls.append(
            {
                "id": int(wall.id()),
                "name": str(wall.name()),
                "position": vector3(wall.pos()),
                "vertices": [
                    {
                        "id": int(vertex.id()),
                        "position": vector3(vertex.pos()),
                    }
                    for vertex in wall.vertices()
                ],
                "facets": [
                    {
                        "id": int(facet.id()),
                        "active": int(facet.active()),
                        "position": vector3(facet.pos()),
                        "normal": vector3(facet.normal()),
                        # Vertex topology is required to rebuild real wall
                        # faces downstream. Without it the viewer can only
                        # draw the loose vertex polyline as rods.
                        "vertex_ids": [
                            int(vertex.id()) for vertex in facet.vertices()
                        ],
                    }
                    for facet in wall.facets()
                ],
            }
        )
    walls.sort(key=lambda row: row["id"])
    return {"count": len(walls), "walls": walls}


AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


def resolve_wall_roles(config: dict[str, Any], walls: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick the loading platens. Never assumes Wall IDs 1 and 2.

    Order: explicit config IDs, then Walls named top/bottom, then the Walls
    with the highest and lowest position along ``load_axis`` (default z).
    The frame index columns ``wall1_*``/``top_force_magnitude`` hold the top
    role; ``wall2_*``/``bottom_force_magnitude`` hold the bottom role.
    Wall-less models are captured without Wall or aggregate-force channels.
    """
    configured_axis = config.get("load_axis")
    if configured_axis is None and int(itasca.dim()) == 2:
        # PFC2D has no physical z axis; every Wall position has z=0.  Sorting
        # platen roles along z would silently pick side Walls as top/bottom.
        axis = "y"
    else:
        axis = str(configured_axis or "z").lower()
    if axis not in AXIS_INDEX:
        raise ValueError(f"load_axis must be x, y or z, got {axis!r}")
    if not walls:
        return {"top": None, "bottom": None, "axis": axis, "source": "no-walls"}
    ids = {int(w["id"]) for w in walls}
    top_id, bottom_id = config.get("top_wall_id"), config.get("bottom_wall_id")
    if top_id is not None and bottom_id is not None:
        top_id, bottom_id = int(top_id), int(bottom_id)
        source = "config"
    else:
        named = {str(w.get("name", "")).lower(): int(w["id"]) for w in walls}
        if "top" in named and "bottom" in named:
            top_id, bottom_id, source = named["top"], named["bottom"], "name"
        else:
            if len(walls) < 2:
                raise RuntimeError(
                    "Need at least two Walls to find loading platens; set "
                    "top_wall_id and bottom_wall_id in the case config"
                )
            k = AXIS_INDEX[axis]
            ordered = sorted(walls, key=lambda w: float(w["position"][k]))
            bottom_id, top_id = int(ordered[0]["id"]), int(ordered[-1]["id"])
            source = f"position-{axis}"
    if top_id == bottom_id or top_id not in ids or bottom_id not in ids:
        raise RuntimeError(f"Invalid platen Wall IDs: top={top_id} bottom={bottom_id}")
    return {"top": top_id, "bottom": bottom_id, "axis": axis, "source": source}


def read_histories(config: dict[str, Any]) -> dict[str, Any]:
    """Read native model histories named in config ``history_names``.

    Default is ["1", "2", "3"]; use [] when the model defines none. Optional
    ``history_meanings`` maps name -> {"physical_meaning", "unit"}.
    """
    names = [str(n) for n in config.get("history_names", ["1", "2", "3"])]
    meanings = config.get("history_meanings", {})
    definitions, arrays = {}, {}
    for name in names:
        meaning = meanings.get(name, {})
        definitions[name] = {
            "physical_meaning": meaning.get("physical_meaning", f"model history {name}"),
            "unit": meaning.get("unit", ""),
            "source": f"model history name '{name}'",
        }
        history = itasca.history.get(name)
        if len(history.shape) != 2 or history.shape[1] < 2:
            raise RuntimeError(f"History {name} has unexpected shape {history.shape}")
        arrays[name] = [[float(row[0]), float(row[1])] for row in history.tolist()]
    return {"definitions": definitions, "arrays": arrays}


def write_csv(path: Path, header: list[str], rows: list[list[Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def install_capture(
    run_dir: Path,
    stride_cycles: int,
    roles: dict[str, Any],
    *,
    sample_mode: str = "cycle",
    sample_value: float = 1.0,
    capture_contacts: bool = False,
) -> None:
    itasca.fish.set(
        "_pfc_live_capture_frame_path",
        fish_path(run_dir / "raw" / "ball_frames.csv"),
    )
    itasca.fish.set(
        "_pfc_live_capture_index_path",
        fish_path(run_dir / "raw" / "frame_index.csv"),
    )
    itasca.fish.set(
        "_pfc_live_capture_walls_path",
        fish_path(run_dir / "raw" / "wall_vertices.csv"),
    )
    itasca.fish.set(
        "_pfc_live_capture_contacts_path",
        fish_path(run_dir / "raw" / "contact_frames.csv"),
    )
    itasca.command(
        """
fish define _pfc_live_capture_init
  global _pfc_live_capture_enabled = true
  global _pfc_live_capture_frame_id = 0
  global _pfc_live_capture_stride = 500
  global _pfc_live_capture_mode = 'cycle'
  global _pfc_live_capture_value = 1.0
  global _pfc_live_capture_last_cycle = -1
  global _pfc_live_capture_last_time = -1.0
  global _pfc_live_capture_calls = 0
  global _pfc_live_capture_events = 0
  global _pfc_live_capture_contacts = false
  global _pfc_live_capture_wall_top = 1
  global _pfc_live_capture_wall_bottom = 2
  global _pfc_live_capture_3d = false
end

fish define _pfc_live_capture_endpoint_ball_id(piece)
  if type.pointer(piece) = 'ball' then
    _pfc_live_capture_endpoint_ball_id = ball.id(piece)
  else
    _pfc_live_capture_endpoint_ball_id = -1
  endif
end

fish define _pfc_live_capture_vel_z(v)
  if _pfc_live_capture_3d = true then
    _pfc_live_capture_vel_z = comp.z(v)
  else
    _pfc_live_capture_vel_z = 0.0
  endif
end

fish define _pfc_live_capture_spin_x(v)
  if _pfc_live_capture_3d = true then
    _pfc_live_capture_spin_x = comp.x(v)
  else
    _pfc_live_capture_spin_x = 0.0
  endif
end

fish define _pfc_live_capture_spin_y(v)
  if _pfc_live_capture_3d = true then
    _pfc_live_capture_spin_y = comp.y(v)
  else
    _pfc_live_capture_spin_y = 0.0
  endif
end

fish define _pfc_live_capture_spin_z(v)
  if _pfc_live_capture_3d = true then
    _pfc_live_capture_spin_z = comp.z(v)
  else
    _pfc_live_capture_spin_z = v
  endif
end

fish define _pfc_live_capture_z(v)
  if _pfc_live_capture_3d = true then
    _pfc_live_capture_z = comp.z(v)
  else
    _pfc_live_capture_z = 0.0
  endif
end

fish define _pfc_live_capture_frame
  if _pfc_live_capture_enabled = false then
    exit
  endif
  _pfc_live_capture_frame_id = _pfc_live_capture_frame_id + 1
  local fid = _pfc_live_capture_frame_id
  local cyc = mech.cycle()
  local mt = mech.time.total()
  _pfc_live_capture_last_cycle = cyc
  _pfc_live_capture_last_time = mt

  local bf = file.open(_pfc_live_capture_frame_path,'append','text')
  local brows = list()
  loop foreach local b ball.list
    local bv = ball.vel(b)
    local bs = ball.spin(b)
    brows = list.append(brows,string.build('%1,%2,%3,%4,%5,%6,%7,%8,%9', ...
      fid,ball.id(b),comp.x(ball.pos(b)),comp.y(ball.pos(b)), ...
      _pfc_live_capture_z(ball.pos(b)),ball.radius(b), ...
      comp.x(bv),comp.y(bv),_pfc_live_capture_vel_z(bv)) + ',' + ...
      string.build('%1,%2,%3',_pfc_live_capture_spin_x(bs), ...
      _pfc_live_capture_spin_y(bs),_pfc_live_capture_spin_z(bs)))
  endloop
  file.write(bf,brows)
  file.close(bf)

  local wf = file.open(_pfc_live_capture_walls_path,'append','text')
  local wrows = list()
  loop foreach local v wall.vertex.list()
    local wp = wall.vertex.pos(v)
    wrows = list.append(wrows,string.build('%1,%2,%3,%4,%5', ...
      fid,wall.vertex.id(v),comp.x(wp),comp.y(wp),_pfc_live_capture_z(wp)))
  endloop
  file.write(wf,wrows)
  file.close(wf)

  if _pfc_live_capture_contacts = true then
    local cf = file.open(_pfc_live_capture_contacts_path,'append','text')
    local crows = list()
    loop foreach local c contact.list
      local cp = contact.pos(c)
      local cforce = contact.force.global(c)
      local e1 = contact.end1(c)
      local e2 = contact.end2(c)
      local end1_ball = _pfc_live_capture_endpoint_ball_id(e1)
      local end2_ball = _pfc_live_capture_endpoint_ball_id(e2)
      crows = list.append(crows,string.build('%1,%2,%3,%4,%5,%6,%7,%8,%9', ...
        fid,contact.id(c),type.pointer(e1),end1_ball, ...
        type.pointer(e2),end2_ball,comp.x(cp),comp.y(cp), ...
        _pfc_live_capture_z(cp)) + ',' + ...
        string.build('%1,%2,%3,%4',comp.x(cforce),comp.y(cforce), ...
        _pfc_live_capture_vel_z(cforce),contact.model(c)))
    endloop
    file.write(cf,crows)
    file.close(cf)
  endif

  local ix = file.open(_pfc_live_capture_index_path,'append','text')
  local irow = list()
  if _pfc_live_capture_wall_top > 0 then
    local w1 = wall.find(_pfc_live_capture_wall_top)
    local w2 = wall.find(_pfc_live_capture_wall_bottom)
    local p1 = wall.pos(w1)
    local p2 = wall.pos(w2)
    local f1 = wall.force.contact(w1)
    local f2 = wall.force.contact(w2)
    irow = list.append(irow,string.build('%1,%2,%3,%4,%5,%6,%7,%8,%9', ...
      fid,cyc,mt,ball.num(),comp.x(p1),comp.y(p1),_pfc_live_capture_z(p1), ...
      comp.x(p2),comp.y(p2)) + ',' + string.build('%1,%2,%3,%4', ...
      _pfc_live_capture_z(p2),math.mag(f1),math.mag(f2),_pfc_live_capture_calls) + ',' + ...
      string.build('%1,%2',_pfc_live_capture_mode,_pfc_live_capture_value))
  else
    irow = list.append(irow,string.build('%1,%2,%3,%4,,,,,,,,,%5', ...
      fid,cyc,mt,ball.num(),_pfc_live_capture_calls) + ',' + ...
      string.build('%1,%2',_pfc_live_capture_mode,_pfc_live_capture_value))
  endif
  file.write(ix,irow)
  file.close(ix)
end

fish define _pfc_live_capture_cycle
  _pfc_live_capture_calls = _pfc_live_capture_calls + 1
  if _pfc_live_capture_enabled = true then
    if _pfc_live_capture_mode = 'cycle' then
      if (mech.cycle() - _pfc_live_capture_last_cycle) >= _pfc_live_capture_stride then
        _pfc_live_capture_frame
      endif
    else
      if _pfc_live_capture_mode = 'time' then
        if (mech.time.total() - _pfc_live_capture_last_time) >= _pfc_live_capture_value then
          _pfc_live_capture_frame
        endif
      endif
    endif
  endif
end
"""
    )
    itasca.fish.call_function("_pfc_live_capture_init")
    itasca.fish.set("_pfc_live_capture_stride", int(stride_cycles))
    itasca.fish.set("_pfc_live_capture_mode", sample_mode)
    itasca.fish.set("_pfc_live_capture_value", float(sample_value))
    itasca.fish.set("_pfc_live_capture_contacts", bool(capture_contacts))
    itasca.fish.set("_pfc_live_capture_3d", int(itasca.dim()) == 3)
    itasca.fish.set(
        "_pfc_live_capture_wall_top",
        int(roles["top"]) if roles["top"] is not None else -1,
    )
    itasca.fish.set(
        "_pfc_live_capture_wall_bottom",
        int(roles["bottom"]) if roles["bottom"] is not None else -1,
    )
    itasca.command(f"fish callback remove {CAPTURE_CALLBACK} {CAPTURE_POSITION}")
    itasca.command(f"fish callback add {CAPTURE_CALLBACK} {CAPTURE_POSITION}")


def install_fracture_observer(run_dir: Path) -> None:
    itasca.fish.set(
        "_pfc_live_capture_events_path",
        fish_path(run_dir / "raw" / "fracture_events.csv"),
    )
    itasca.command(
        """
fish define _pfc_live_capture_bond(entries)
  if _pfc_live_capture_enabled = false then
    exit
  endif
  local contact = entries(1)
  local p = contact.pos(contact)
  local n = contact.normal(contact)
  local size = contact.prop(contact,'pb_radius')
  local endpoint1 = contact.end1(contact)
  local endpoint2 = contact.end2(contact)
  local ball_a = _pfc_live_capture_endpoint_ball_id(endpoint1)
  local ball_b = _pfc_live_capture_endpoint_ball_id(endpoint2)
  _pfc_live_capture_events = _pfc_live_capture_events + 1
  local f = file.open(_pfc_live_capture_events_path,'append','text')
  local row = list()
  row = list.append(row,string(_pfc_live_capture_events) + ',' + ...
    string(mech.cycle()) + ',' + string(mech.time.total()) + ',' + ...
    string(contact.id(contact)) + ',' + string(ball_a) + ',' + string(ball_b) + ',' + ...
    string(entries(2)) + ',' + string(entries(3)) + ',' + ...
    string(comp.x(p)) + ',' + string(comp.y(p)) + ',' + string(_pfc_live_capture_z(p)) + ',' + ...
    string(comp.x(n)) + ',' + string(comp.y(n)) + ',' + string(_pfc_live_capture_z(n)) + ',' + ...
    string(size))
  file.write(f,row)
  file.close(f)
  if _pfc_live_capture_mode = 'event' then
    _pfc_live_capture_frame
  endif
end
"""
    )
    itasca.command(f"fish callback remove {CAPTURE_BOND} event bond_break")
    itasca.command(f"fish callback add {CAPTURE_BOND} event bond_break")


def stop_capture() -> None:
    if itasca.fish.has(CAPTURE_CALLBACK):
        itasca.command(f"fish callback remove {CAPTURE_CALLBACK} {CAPTURE_POSITION}")
    if itasca.fish.has(CAPTURE_BOND):
        itasca.command(f"fish callback remove {CAPTURE_BOND} event bond_break")
    if itasca.fish.has("_pfc_live_capture_enabled"):
        itasca.fish.set("_pfc_live_capture_enabled", False)


def publish_native_histories(
    run_dir: Path, histories: dict[str, Any], time_history: str = "1"
) -> int:
    rows = []
    for history_id in histories["arrays"]:
        for cycle, value in histories["arrays"][history_id]:
            rows.append(
                [
                    history_id,
                    int(cycle),
                    float(value),
                    float(value) if history_id == time_history else "",
                    "SAME_NATIVE_ROW" if history_id == time_history else "TIME_NOT_IN_ROW",
                ]
            )
    write_csv(
        run_dir / "native_histories.csv",
        ["history_id", "cycle", "value", "mechanical_time_total", "time_alignment"],
        rows,
    )
    return len(rows)


def publish_fractures_final(run_dir: Path) -> int:
    # PFC2D has no `itasca.dfn` catalog. PFC3D's dfn module may exist but stay
    # empty when bond breaks are captured only by the FISH event callback. In
    # both cases the FISH event rows are the authoritative real PFC fracture
    # record, so derive a catalog from those events when no DFN catalog rows
    # were generated. This preserves real positions, modes and strengths and
    # lets the validator cross-check events against a one-to-one catalog.
    rows = []
    if hasattr(itasca, "dfn"):
        for fracture in itasca.dfn.fracture.list():
            rows.append(
                {
                    "id": int(fracture.id()),
                    "dfn_name": str(fracture.dfn().name()),
                    "position": vector3(fracture.pos()),
                    "normal": vector3(fracture.normal()),
                    "diameter": float(fracture.diameter()),
                    "dip": float(fracture.dip()),
                    "dipdir": float(fracture.dipdir()),
                    "area": float(fracture.area()),
                    "age": float(fracture.prop("age")),
                    "failure_strength": float(fracture.prop("failure_strength")),
                }
            )
    if not rows:
        event_path = run_dir / "raw" / "fracture_events.csv"
        if event_path.is_file():
            with event_path.open(encoding="utf-8", newline="") as handle:
                for event in csv.DictReader(handle):
                    mode = int(float(event["mode"]))
                    rows.append(
                        {
                            "id": int(event["event_id"]),
                            "dfn_name": "pfc_bond_break_tension" if mode == 1 else "pfc_bond_break_shear",
                            "position": [
                                float(event["x"]),
                                float(event["y"]),
                                float(event["z"]),
                            ],
                            "normal": [
                                float(event["nx"]),
                                float(event["ny"]),
                                float(event["nz"]),
                            ],
                            "diameter": float(event["diameter"]),
                            "dip": 0.0,
                            "dipdir": 0.0,
                            "area": math.pi * (float(event["diameter"]) / 2.0) ** 2,
                            "age": float(event["mechanical_time_total"]),
                            "failure_strength": float(event["failure_strength"]),
                        }
                    )
    rows.sort(key=lambda row: row["id"])
    write_json(run_dir / "fractures_final.json", rows)
    return len(rows)


def solve_segmented(config: dict[str, Any], started: float) -> dict[str, Any]:
    """Run the solve in bounded-cycle segments so the bridge stays responsive.

    A single ``model solve time T`` is submitted as one Itasca command; the
    bridge's FISH callback interrupt can only run between commands, so a long
    solve makes check_task_status/interrupt_task time out.  When
    ``solve_segment_cycles`` is a positive integer, the solve command is
    converted to repeated ``model solve cycles N`` steps.  Between steps the
    engine returns to the bridge and can accept an interrupt.

    The time target is parsed from the configured solve command (only the
    ``model solve time <T>`` form is segmented).  Other solve forms are run
    as-is and ``segmented=False`` is reported.
    """
    solve_command = str(config["solve"]).strip()
    max_cycles = int(config.get("solve_segment_cycles", 0) or 0)
    result: dict[str, Any] = {
        "segmented": False,
        "segments": 0,
        "cycles": 0,
        "max_cycles_per_segment": max_cycles,
        "reason": None,
    }
    match = re.match(r"^model\s+solve\s+time\s+([0-9.eE+-]+)\s*$", solve_command)
    if max_cycles <= 0 or not match:
        result["reason"] = (
            "solve_segment_cycles not set"
            if max_cycles <= 0
            else "solve command is not 'model solve time <T>'"
        )
        itasca.command(solve_command)
        return result

    target_time = float(match.group(1))
    initial = float(itasca.mech_age())
    target = initial + target_time
    result["segmented"] = True
    result["target_mechanical_time"] = target
    max_segments = int(config.get("solve_max_segments", 10000) or 10000)
    while float(itasca.mech_age()) < target - 1.0e-12:
        if result["segments"] >= max_segments:
            raise RuntimeError(
                f"Segmented solve exceeded solve_max_segments={max_segments}: "
                f"mechanical_time={itasca.mech_age()} target={target}. "
                "Check timestep/parameter scaling."
            )
        before = int(itasca.cycle())
        itasca.command(f"model solve cycles {max_cycles}")
        advanced = int(itasca.cycle()) - before
        if advanced <= 0:
            raise RuntimeError("Segmented solve made no cycle progress; refusing to spin.")
        result["segments"] += 1
        result["cycles"] += advanced
        time.sleep(0.0)
    result["elapsed_seconds"] = time.perf_counter() - started
    return result


def find_config() -> Path:
    explicit = os.environ.get("PFC_LIVE_CAPTURE_CONFIG")
    if explicit:
        return Path(explicit).resolve()
    sidecar = Path(__file__).resolve().with_name("capture_config.json")
    if not sidecar.is_file():
        raise FileNotFoundError(
            "Pass --config outside PFC, or place capture_config.json beside "
            f"the copied entry script: {sidecar}"
        )
    return sidecar


def main() -> int:
    config = json.loads(find_config().read_text(encoding="utf-8"))
    case_id = int(config["case_id"])
    run_id = str(config["run_id"])
    run_dir = Path(config["run_dir"]).resolve()
    stride_cycles = int(config.get("sample_stride_cycles", 500))
    expected_initial = config.get("expected_initial", {})
    source_files = config.get("source_files", {})

    if run_dir.exists():
        raise FileExistsError(f"Capture run directory already exists: {run_dir}")
    (run_dir / "raw").mkdir(parents=True)
    (run_dir / "metadata").mkdir(parents=True)
    write_csv(
        run_dir / "raw" / "ball_frames.csv",
        [
            "frame_id",
            "ball_id",
            "x",
            "y",
            "z",
            "radius",
            "vx",
            "vy",
            "vz",
            "spin_x",
            "spin_y",
            "spin_z",
        ],
        [],
    )
    write_csv(
        run_dir / "raw" / "frame_index.csv",
        [
            "frame_id",
            "cycle",
            "mechanical_time_total",
            "ball_count",
            "wall1_x",
            "wall1_y",
            "wall1_z",
            "wall2_x",
            "wall2_y",
            "wall2_z",
            "top_force_magnitude",
            "bottom_force_magnitude",
            "callback_calls",
            "sample_mode",
            "sample_value",
        ],
        [],
    )
    write_csv(
        run_dir / "raw" / "wall_vertices.csv",
        ["frame_id", "vertex_id", "x", "y", "z"],
        [],
    )
    write_csv(
        run_dir / "raw" / "fracture_events.csv",
        [
            "event_id",
            "cycle",
            "mechanical_time_total",
            "contact_id",
            "ball_id_a",
            "ball_id_b",
            "mode",
            "failure_strength",
            "x",
            "y",
            "z",
            "nx",
            "ny",
            "nz",
            "diameter",
        ],
        [],
    )
    write_csv(
        run_dir / "raw" / "contact_frames.csv",
        [
            "frame_id",
            "contact_id",
            "end1_type",
            "end1_id",
            "end2_type",
            "end2_id",
            "x",
            "y",
            "z",
            "fx",
            "fy",
            "fz",
            "model",
        ],
        [],
    )

    result = {
        "schema_version": SCHEMA_VERSION,
        "data_boundary": DATA_BOUNDARY,
        "case_id": case_id,
        "run_id": run_id,
        "started_utc": utc_now(),
        "config": config,
        "status": "STARTING",
        "errors": [],
        "source_hashes": {},
        "pre_snapshot": None,
        "post_snapshot": None,
        "capture": None,
        "save_executed": False,
    }
    try:
        for name, expected in source_files.items():
            path = Path(config["project_dir"]) / name
            actual = sha256_file(path)
            result["source_hashes"][name] = {
                "path": str(path),
                "expected": expected,
                "actual": actual,
                "match": actual == expected,
            }
            if actual != expected:
                raise RuntimeError(f"Source hash mismatch: {name}")

        if bool(config.get("restore_initial", False)):
            itasca.command("model restore 'initial'")

        for command in config.get("setup", []):
            itasca.command(command)

        result["pre_snapshot"] = snapshot()
        for key, expected in expected_initial.items():
            actual = result["pre_snapshot"][key]
            if actual != expected:
                raise RuntimeError(
                    f"Initial {key} mismatch: {actual!r} != {expected!r}"
                )

        walls_static = read_wall_static()
        roles = resolve_wall_roles(config, walls_static["walls"])
        static = {
            "schema_version": SCHEMA_VERSION,
            "data_boundary": DATA_BOUNDARY,
            "dimension": int(itasca.dim()),
            "case_id": case_id,
            "run_id": run_id,
            "snapshot": result["pre_snapshot"],
            "balls": read_ball_static(),
            "walls": walls_static,
            "histories": read_histories(config)["definitions"],
            "wall_roles": roles,
            "load_axis": roles["axis"],
        }
        write_json(run_dir / "static.json", static)

        sample_mode = str(config.get("sample_mode", "cycle"))
        if sample_mode not in {"cycle", "time", "event"}:
            raise ValueError(f"Unsupported sample_mode: {sample_mode}")
        sample_value = float(
            config.get(
                "sample_interval",
                config.get(
                    "sample_interval_time",
                    config.get("sample_stride_cycles", stride_cycles),
                ),
            )
        )
        if sample_value < 0:
            raise ValueError("sample_interval cannot be negative")
        capture_contacts = bool(config.get("capture_contacts", False))
        install_capture(
            run_dir,
            stride_cycles,
            roles,
            sample_mode=sample_mode,
            sample_value=sample_value,
            capture_contacts=capture_contacts,
        )
        if bool(config.get("fracture_observer", False)) or sample_mode == "event":
            install_fracture_observer(run_dir)

        itasca.fish.call_function(CAPTURE_FRAME)
        started = time.perf_counter()
        segmentation = solve_segmented(config, started)
        result["solve_segmentation"] = segmentation
        solve_elapsed = float(
            segmentation.get("elapsed_seconds")
            or (time.perf_counter() - started)
        )
        for command in config.get("post_solve", []):
            itasca.command(command)
        if int(itasca.fish.get("_pfc_live_capture_last_cycle")) < int(itasca.cycle()):
            itasca.fish.call_function(CAPTURE_FRAME)
        stop_capture()

        result["post_snapshot"] = snapshot()
        result["solve_elapsed_seconds"] = solve_elapsed
        histories = read_histories(config)
        result["native_history_row_count"] = publish_native_histories(
            run_dir, histories, str(config.get("time_history_name", "1"))
        )
        if bool(config.get("fracture_observer", False)) or sample_mode == "event":
            result["fracture_catalog_row_count"] = publish_fractures_final(run_dir)
            result["fracture_catalog_status"] = (
                "NOT_SUPPORTED" if not hasattr(itasca, "dfn") else "GENERATED"
            )

        if config.get("save"):
            itasca.command(config["save"])
            result["save_executed"] = True

        calls = int(itasca.fish.get("_pfc_live_capture_calls"))
        frames = int(itasca.fish.get("_pfc_live_capture_frame_id"))
        events = int(itasca.fish.get("_pfc_live_capture_events"))
        initial_time = float(result["pre_snapshot"]["mechanical_time_total"])
        final_time = float(result["post_snapshot"]["mechanical_time_total"])
        planned_status = dict(config.get("field_status_plan") or {})
        field_status = {
            "particle_position": "REAL_PFC",
            "particle_radius": "REAL_PFC",
            "particle_velocity": planned_status.get("ball.velocity", "NOT_SELECTED"),
            "particle_spin": planned_status.get("ball.spin", "NOT_SELECTED"),
            "wall_vertices": "REAL_PFC",
            "contact_network": (
                "REAL_PFC" if capture_contacts else "NOT_CAPTURED"
            ),
            "fracture_events": (
                "REAL_PFC"
                if bool(config.get("fracture_observer", False))
                or sample_mode == "event"
                else "NOT_CAPTURED"
            ),
            "fracture_endpoint_ball_ids": (
                "REAL_PFC"
                if bool(config.get("fracture_observer", False))
                or sample_mode == "event"
                else "NOT_CAPTURED"
            ),
        }
        result["capture"] = {
            "callback_calls": calls,
            "frame_count": frames,
            "fracture_event_count": events,
            "mechanical_time_run": final_time - initial_time,
            "sample_stride_cycles": stride_cycles,
            "sample_mode": sample_mode,
            "sample_value": sample_value,
            "sample_interval_mode": (
                "Cycle-stride sampling"
                if sample_mode == "cycle"
                else (
                    "mechanical-time interval sampling"
                    if sample_mode == "time"
                    else "solve/fracture event sampling"
                )
            ),
            "capture_contacts": capture_contacts,
            "field_status": field_status,
            "collection_plan": config.get("collection_plan"),
        }
        if frames < 2:
            raise RuntimeError(f"Capture produced only {frames} frame(s)")
        expected_run = config.get("expected_mechanical_time_run")
        if expected_run is not None and (
            final_time - initial_time < float(expected_run) - 1.0e-8
        ):
            raise RuntimeError(
                "Mechanical Time target was not reached: "
                f"{final_time - initial_time} < {expected_run}"
            )
        result["status"] = "COMPLETE"
    except BaseException as exc:
        result["status"] = "FAILED"
        result["errors"].append(
            {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        try:
            stop_capture()
        except BaseException as cleanup_exc:
            result["errors"].append(
                {
                    "phase": "cleanup",
                    "type": type(cleanup_exc).__name__,
                    "message": str(cleanup_exc),
                }
            )
        try:
            result["post_snapshot"] = snapshot()
        except BaseException:
            pass
    finally:
        result["ended_utc"] = utc_now()
        result["engine"] = {
            "executable": sys.executable,
            "python": platform.python_version(),
            "runtime_mode": "CONSOLE",
        }
        files = []
        for path in sorted(run_dir.rglob("*")):
            if path.is_file() and path.name != "result.json":
                files.append(
                    {
                        "path": path.relative_to(run_dir).as_posix(),
                        "size_bytes": path.stat().st_size,
                        "sha256": sha256_file(path),
                    }
                )
        result["files"] = files
        write_json(run_dir / "metadata" / "result.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0 if result["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    exit_code = main()
    if exit_code:
        raise RuntimeError("PFC capture failed; see metadata/result.json")
