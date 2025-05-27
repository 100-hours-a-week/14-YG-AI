from typing import Any, Dict, List, Callable
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langchain_core.messages import BaseMessage
import json


def _print_separator():
    print("\n" + "=" * 50)


def _format_namespace(ns: List[str]) -> str:
    return ns[-1].split(":")[0] if ns else "root graph"


def stream_graph(
    graph: CompiledStateGraph,
    inputs: dict,
    config: RunnableConfig,
    node_names: List[str] = None,
    callback: Callable[[Dict[str, Any]], None] = None,
):
    """
    LangGraph의 'messages' 스트림을 받아 노드별로 실시간 출력합니다.
    node_names에 특정 노드를 지정하면 해당 노드만, 아니면 전체 노드를 출력합니다.
    """
    node_names = node_names or []
    prev_node = None

    for chunk_msg, meta in graph.stream(inputs, config, stream_mode="messages"):
        node = meta["langgraph_node"]
        if node_names and node not in node_names:
            continue

        if callback:
            callback({"node": node, "content": chunk_msg.content})
        else:
            if node != prev_node:
                _print_separator()
                print(f"🔄 Node: \033[1;36m{node}\033[0m 🔄")
                print("-" * 25)
            print(chunk_msg.content, end="", flush=True)

        prev_node = node


def invoke_graph(
    graph: CompiledStateGraph,
    inputs: dict,
    config: RunnableConfig,
    node_names: List[str] = None,
    callback: Callable[[Dict[str, Any]], None] = None,
):
    """
    LangGraph의 'updates' 스트림을 받아 최종 노드 결과를 예쁘게 출력합니다.
    subgraphs=True로 서브그래프 결과까지 포함하며, node_names로 필터링할 수 있습니다.
    """
    node_names = node_names or []

    for namespace, chunk in graph.stream(
        inputs, config, stream_mode="updates", subgraphs=True
    ):
        for node, data in chunk.items():
            if node_names and node not in node_names:
                continue

            if callback:
                callback({"node": node, "content": data})
            else:
                _print_separator()
                formatted_ns = _format_namespace(namespace)
                ns_label = (
                    f" in [\033[1;33m{formatted_ns}\033[0m]"
                    if formatted_ns != "root graph"
                    else ""
                )
                print(f"🔄 Node: \033[1;36m{node}\033[0m{ns_label} 🔄")
                print("-" * 25)

                # dict → 키별로, list → 아이템별로, 그 외 → 그대로 출력
                if isinstance(data, dict):
                    for v in data.values():
                        if isinstance(v, BaseMessage):
                            v.pretty_print()
                        else:
                            print(v)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, BaseMessage):
                            item.pretty_print()
                        else:
                            print(item)
                else:
                    print(data)


def invoke_graph_clean(
    graph: CompiledStateGraph,
    inputs: dict,
    config: RunnableConfig,
    node_names: List[str] = None,
    callback: Callable[[Dict[str, Any]], None] = None,
):
    """
    LangGraph의 'updates' 스트림을 받아 최종 노드 결과를 예쁘게 출력합니다.
    subgraphs=True로 서브그래프 결과까지 포함하며, node_names로 필터링할 수 있습니다.
    """
    node_names = node_names or []
    try:
        for namespace, chunk in graph.stream(
            inputs, config, stream_mode="updates", subgraphs=True
        ):
            for node, data in chunk.items():
                if node_names and node not in node_names:
                    continue

                if callback:
                    callback({"node": node, "content": data})
                else:
                    # _print_separator()
                    formatted_ns = _format_namespace(namespace)
                    ns_label = (
                        f" in [\033[1;33m{formatted_ns}\033[0m]"
                        if formatted_ns != "root graph"
                        else ""
                    )

                    # dict → 키별로, list → 아이템별로, 그 외 → 그대로 출력
                    if isinstance(data, dict):
                        for v in data.values():
                            if isinstance(v, BaseMessage):
                                v.pretty_print()
                            else:
                                print(v)
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, BaseMessage):
                                item.pretty_print()
                            else:
                                print(item)
                    else:
                        print(data)
    except Exception as e:
        print(f"====error====\n{e}")


def invoke_graph_json(
    graph: CompiledStateGraph,
    inputs: dict,
    config: RunnableConfig,
    node_names: List[str] = None,
    callback: Callable[[Dict[str, Any]], None] = None,
) -> Any:
    """
    LangGraph의 'updates' 스트림을 돌면서,
    node_names에 해당하는 노드가 방출하는 마지막 data만 반환합니다.
    중간 과정은 전혀 출력하지 않습니다.
    """
    node_names = set(node_names or [])
    result = None

    try:
        for _, chunk in graph.stream(
            inputs, config, stream_mode="updates", subgraphs=True
        ):
            for node, data in chunk.items():
                # node_names가 비어있다면 모든 노드를 대상으로,
                # 아니면 지정된 노드만 대상으로 업데이트
                if not node_names or node in node_names:
                    result = data
        # 스트림이 끝날 때까지 돌고 나면 마지막으로 기록된 result를 반환
        print(json.dumps(result, indent=4, ensure_ascii=False))
        return result

    except Exception as e:
        print("공고글을 생성할 수 없습니다")
        return e
    

def invoke_graph_json_test(
    graph: CompiledStateGraph,
    inputs: dict,
    config: RunnableConfig,
    node_names: List[str] = None,
    callback: Callable[[Dict[str, Any]], None] = None,
) -> Any:
    """
    LangGraph의 'updates' 스트림을 돌면서,
    node_names에 해당하는 노드가 방출하는 마지막 data만 반환합니다.
    중간 과정은 전혀 출력하지 않습니다.
    """
    node_names = set(node_names or [])
    result = None

    for _, chunk in graph.stream(
        inputs, config, stream_mode="updates", subgraphs=True
    ):
        for node, data in chunk.items():
            # node_names가 비어있다면 모든 노드를 대상으로,
            # 아니면 지정된 노드만 대상으로 업데이트
            if not node_names or node in node_names:
                result = data
    # 스트림이 끝날 때까지 돌고 나면 마지막으로 기록된 result를 반환
    print(json.dumps(result, indent=4, ensure_ascii=False))
    return result


