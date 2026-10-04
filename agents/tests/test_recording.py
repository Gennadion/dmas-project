"""The demo recording (demo/run.json) and the page's own verification code.

Records a real run on the test chain, then runs demo/verify.js -- the exact
code the GitHub Pages demo runs in visitors' browsers -- over it via
demo/check-recording.mjs. Tampered recordings must fail verification.
"""

import copy
import json
import shutil
import subprocess

import pytest

from dmas.chain import BLOCKCHAIN_DIR, LOCAL_CHAIN_IDS, Chain, hardhat_accounts
from dmas.chain_topology import did_for, example_chain_topology
from dmas.discovery import run_discovery
from dmas.recording import record
from dmas.termination import max_communications
from dmas.types import Request
from tests.conftest import TEST_NODE_PORT

CHECKER = BLOCKCHAIN_DIR.parent / "demo" / "check-recording.mjs"
ACCOUNTS = hardhat_accounts(8)
PA_DID = did_for("pa-test")


@pytest.fixture(scope="module")
def recorded(w3) -> dict:
    chain = Chain.deploy(w3, ACCOUNTS[0])
    topology = example_chain_topology(chain, ACCOUNTS)
    topology.register_all(PA_DID)
    runs = [
        run_discovery(Request("code", "payload"), topology, strategy, max_communications(3))
        for strategy in ("dfs", "bfs")
    ]
    return record(topology, PA_DID, runs)


@pytest.fixture
def recording(recorded) -> dict:
    """A private copy per test, so tampering tests can't leak into others."""
    return copy.deepcopy(recorded)


def _check(recording: dict, tmp_path) -> subprocess.CompletedProcess:
    path = tmp_path / "run.json"
    path.write_text(json.dumps(recording))
    return subprocess.run(
        [shutil.which("node"), str(CHECKER), str(path), f"http://127.0.0.1:{TEST_NODE_PORT}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )


def test_recording_covers_every_exchange(recording):
    assert recording["chainId"] == 31337
    assert recording["explorer"] is None
    for run in recording["runs"]:
        assert len(run["exchanges"]) == 3  # max_communications(3)
        assert run["exchanges"][0]["terminal"] is False  # the routing SA
        assert all(len(tx) == 66 for e in run["exchanges"] for tx in e["txs"].values())


def test_recording_holds_no_secrets(recording):
    text = json.dumps(recording)
    assert "127.0.0.1" not in text  # no RPC URL
    assert "junk" not in text  # no mnemonic
    assert ACCOUNTS[0].key.hex().removeprefix("0x") not in text  # no private key


def test_page_verification_passes_on_a_genuine_recording(recording, tmp_path):
    result = _check(recording, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "all checks passed" in result.stdout


@pytest.mark.parametrize(
    "tamper, failing_check",
    [
        (lambda e, run: run.__setitem__("requestBytes", run["requestBytes"][:-2] + "00"), "Request commitment"),
        (lambda e, run: e.__setitem__("ciphertext", e["ciphertext"][:-2] + "00"), "Response commitment"),
        (lambda e, run: e.__setitem__("key", "0x" + "11" * 32), "decrypts"),
        (lambda e, run: e["response"].__setitem__("payload", "forged"), "decrypts"),
    ],
)
def test_page_verification_catches_tampering(recording, tmp_path, tamper, failing_check):
    run = recording["runs"][0]
    tamper(run["exchanges"][-1], run)

    result = _check(recording, tmp_path)
    assert result.returncode == 1
    failures = [line for line in result.stdout.splitlines() if line.startswith("FAIL")]
    assert any(failing_check in line for line in failures), result.stdout


def test_committed_demo_recording_is_from_a_public_chain():
    """demo/run.json is what GitHub Pages publishes; a local-node recording
    would link to transactions nobody else can see."""
    path = CHECKER.parent / "run.json"
    if not path.exists():
        pytest.skip("no demo recording committed yet")
    assert json.loads(path.read_text())["chainId"] not in LOCAL_CHAIN_IDS
