"""Session-scoped throwaway Hardhat node for the on-chain tests.

Runs on its own port so it never collides with a `npx hardhat node` you
have open on 8545. Tests that need it are skipped (not failed) if Node or
the compiled Hardhat project isn't available.
"""

import shutil
import subprocess
import time

import pytest
from web3 import Web3

from dmas.chain import ARTIFACTS_DIR, BLOCKCHAIN_DIR

TEST_NODE_PORT = 8546
HARDHAT_CLI = BLOCKCHAIN_DIR / "node_modules" / "hardhat" / "internal" / "cli" / "bootstrap.js"


@pytest.fixture(scope="session")
def w3():
    node = shutil.which("node")
    if node is None or not HARDHAT_CLI.exists():
        pytest.skip("Node.js / blockchain/node_modules not available -- run `npm install` in blockchain/")
    if not ARTIFACTS_DIR.exists():
        pytest.skip("contracts not compiled -- run `npm run compile` in blockchain/")

    proc = subprocess.Popen(
        [node, str(HARDHAT_CLI), "node", "--port", str(TEST_NODE_PORT)],
        cwd=BLOCKCHAIN_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    w3 = Web3(Web3.HTTPProvider(f"http://127.0.0.1:{TEST_NODE_PORT}"))
    deadline = time.monotonic() + 60
    while not w3.is_connected():
        if proc.poll() is not None or time.monotonic() > deadline:
            proc.kill()
            pytest.fail("Hardhat node did not start")
        time.sleep(0.25)

    yield w3

    proc.kill()
    proc.wait()
