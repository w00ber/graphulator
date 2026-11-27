"""Layer 0 step 3, slice 3: the scattering-code export is rendered from the model.

Gate: for every shipped .pgraph, the script ``scattering_script(load(path))``
writes, when run, gives the S that Show S computes for the same document
(``compute_job`` over ``compile_jobs``) bit for bit, with the same port
order. Qt-free; the GUI wiring is tested in test_gui_show_s_model.py.
"""
import logging
import os

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")

from graphulator import model as M  # noqa: E402
from graphulator.model.export_script import scattering_script  # noqa: E402
from graphulator.model.legacy_job import compile_jobs, compute_job  # noqa: E402
from tests.test_model_legacy_job import FILES, IDS, PG  # noqa: E402

PLOT_MARKERS = ("# Plot S-parameters", "# Add traces to each component's GSM")


def _head(code):
    """The script up to its plotting section."""
    for m in PLOT_MARKERS:
        if m in code:
            return code.split(m)[0].rsplit("# ====", 1)[0]
    raise AssertionError("no plotting section")


def _run_script(code, full=False):
    ns = {"__name__": "__exported__"}
    exec(compile(code if full else _head(code), "<exported>", "exec"), ns)
    if "gsm_components" in ns:
        return ns, dict(ns["gsm_components"])
    return ns, {None: ns["scattering_matrix"]}


def _check(doc, **kw):
    jobs = compile_jobs(doc, **{k: v for k, v in kw.items() if k != "traces"})
    code = scattering_script(doc, **kw)
    logging.disable(logging.WARNING)
    try:
        _, gsms = _run_script(code)
        want = [compute_job(j) for j in jobs]
    finally:
        logging.disable(logging.NOTSET)
    keys = [None] if len(jobs) == 1 else [j["component_index"] for j in jobs]
    assert list(gsms) == keys
    for key, res in zip(keys, want):
        g = gsms[key]
        if res is None:
            assert g is None
            continue
        assert np.array_equal(g.S, res["S"])
        assert list(g.port_ids) == res["port_ids"]
    return code


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_exported_script_is_show_s(path):
    _check(M.load(path))


def test_custom_grid_and_tail_closure_reach_the_script():
    doc = M.load(os.path.join(PG, "TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph"))
    f = np.linspace(4.0, 5.0, 37)
    code = _check(doc, f_root_s=f, tail_closure=False)
    assert "np.linspace(4.0, 5.0, 37)" in code and "tail_closure=False" in code
    assert "conj=True" in code and "'frame_rule': 'sector'" in code


def test_conjugated_root_flips_the_sweep():
    """TEUFELATOR's saved root (node 6) and the alternative root 4 differ in
    sector; the old exporter ignored the flip, the script follows Show S."""
    doc = M.load(os.path.join(PG, "TEUFELATOR.pgraph"))
    _check(doc)
    doc.solve.root = "n4"
    _check(doc)


def test_constraint_groups_become_shared_variables():
    doc = M.load(os.path.join(PG, "DELTA_AMP_WIDE.pgraph"))
    code = _check(doc)
    assert "gP_group1 = 0.078" in code
    assert "'rate': gP_group1" in code and "'rate': gP_group2" in code


def test_constraint_variable_only_where_the_value_agrees():
    doc = M.load(os.path.join(PG, "DELTA_AMP_WIDE.pgraph"))
    # a member edited away from its group's value keeps its own literal
    coup = next(c for c in doc.couplings if c.rate == 0.047)
    coup.rate = 0.05
    code = _check(doc)
    assert "'rate': 0.05" in code and "gP_group2" in code


def test_multicomponent_and_selected_traces():
    doc = M.load(os.path.join(PG, "TL_5_TWO_LINES_ONE_PORT.pgraph"))
    code = _check(doc, traces=[(1, 0, 0)])
    assert "gsm_components[1].add_trace(0, 0," in code
    assert "gsm_components[0].add_trace" not in code


def test_full_script_runs_with_plotting():
    import matplotlib.pyplot as plt
    # The script ends in plt.show(). Once an earlier test has imported
    # PySide6, matplotlib picks QtAgg and show() enters the Qt event loop and
    # never returns (the suite hung here); render off screen instead.
    backend = plt.get_backend()
    plt.switch_backend("Agg")
    try:
        _run_plotting_scripts(plt)
    finally:
        plt.switch_backend(backend)


def _run_plotting_scripts(plt):
    for name in ("5MODE_CHEBY.pgraph", "TL_5_TWO_LINES_ONE_PORT.pgraph"):
        code = scattering_script(M.load(os.path.join(PG, name)))
        logging.disable(logging.WARNING)
        try:
            _run_script(code, full=True)
        finally:
            logging.disable(logging.NOTSET)
        plt.close("all")


def test_exporter_imports_no_qt():
    import subprocess
    import sys
    code = ("import sys, graphulator.model.export_script; "
            "sys.exit(any(m.startswith('PySide6') for m in sys.modules))")
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0
