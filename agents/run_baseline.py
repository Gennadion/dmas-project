"""Demo entry point: runs the Ding et al. III-B.1 discovery algorithm, both
strategies, over the example topology, printing each step -- same
"watch it happen in the terminal" ethos as `npx hardhat node` in Steps 1-2.
"""

from dmas.proxy_agent import ProxyAgent
from dmas.termination import any_of, max_communications, min_terminal_responses
from dmas.topology import example_topology
from dmas.types import Request


def run(strategy: str) -> None:
    print(f"\n=== {strategy.upper()} discovery ===")
    topology = example_topology()
    pa = ProxyAgent(user_id="user-1", topology=topology)
    request = Request(capability="code", payload="review this pull request")

    termination = any_of(min_terminal_responses(2), max_communications(10))
    responses = pa.discover(request, strategy=strategy, termination=termination)

    trace = pa.context[-1]["trace"]
    for line in trace:
        print(f"  {line}")

    print(f"  R (terminal responses, in order): {[r.sa_id for r in responses]}")


def main() -> None:
    run("dfs")
    run("bfs")


if __name__ == "__main__":
    main()
