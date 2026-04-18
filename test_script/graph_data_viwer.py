from rdflib import Graph, Literal
import json
import tempfile
import webbrowser
import os
from urllib.parse import unquote


def visualize_graph(graph):
    # 提取所有节点和边
    nodes = set()
    edges = []

    # 生成唯一节点ID和标签
    node_dict = {}
    node_counter = 1

    for s, p, o in graph:
        # 处理主语
        s_label = shorten_uri(s)
        if str(s) not in node_dict:
            if str(s).startswith("person"):
                color = {"background": "#FFB6C1", "border": "#666666"}
            else:
                color = {"background": "#66ccff", "border": "#2B7CE9"}
            node_dict[str(s)] = {"id": node_counter, "label": s_label, "type": "uri", "color": color}
            node_counter += 1

        # 处理宾语（考虑字面量）
        if isinstance(o, Literal):
            continue
        o_label = shorten_uri(o) if not isinstance(o, Literal) else str(o)
        if str(o) not in node_dict:
            node_type = "literal" if isinstance(o, Literal) else "uri"
            if str(o).startswith("person"):
                color = {"background": "#FFB6C1", "border": "#666666"}
            else:
                color = {"background": "#66ccff", "border": "#2B7CE9"}
            node_dict[str(o)] = {"id": node_counter, "label": o_label, "type": node_type, "color": color}
            node_counter += 1

        # 添加边
        edges.append({
            "from": node_dict[str(s)]["id"],
            "to": node_dict[str(o)]["id"],
            "label": shorten_uri(p)
        })

    # 转换数据结构
    nodes = list(node_dict.values())

    # 创建HTML模板
    html_template = f"""
<!DOCTYPE html>
<html>
<head>
     <title>RDF Graph Visualization</title>
        <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
        <style>
            #network-container {{
                width: 100%;
                height: 98vh;
                border: 1px solid lightgray;
            }}
        </style>
</head>
<body>
    <div id="network-container"></div>
    <script>
        // 创建节点和边数据集
        var nodes = new vis.DataSet({json.dumps(nodes)});
        var edges = new vis.DataSet({json.dumps(edges)});

        // 新的配置选项
        var options = {{
            nodes: {{
                shape: "dot",
                size: 20,
                font: {{
                    size: 14
                }},
                borderWidth: 2,
                shadow: true,
                color: {{
                    background: "#D2E5FF",
                    border: "#2B7CE9"
                }}
            }},
            edges: {{
                arrows: "to",
                smooth: {{
                    type: "dynamic"
                }},
                font: {{
                    size: 12,
                    align: "middle"
                }},
                color: "#6A6C6E",
                width: 1.5
            }},
            physics: {{
                enabled: true,
                stabilization: {{
                    enabled: true,
                    iterations: 100
                }},
                solver: "forceAtlas2Based",
                forceAtlas2Based: {{
                    gravitationalConstant: -100,
                    centralGravity: 0.005,
                    springLength: 200,
                    avoidOverlap: 1
                }},
                improvedLayout: false  // 显式关闭改进布局算法
            }},
            layout: {{
                improvedLayout: false  // 双重确保关闭
            }}
        }};

        var container = document.getElementById("network-container");
            var data = {{
                nodes: nodes,
                edges: edges
            }};
        var network = new vis.Network(container, data, options);
    </script>
</body>
</html>
        """

    # 保存到临时文件并打开
    filename = "./graph.html"
    with open(filename, "w", encoding='utf-8') as f:
        f.write(html_template)

    webbrowser.open(f"file://{os.path.abspath(filename)}")


def shorten_uri(uri):
    """将URI简化为最后一部分"""
    uri_str = str(unquote(uri))
    # for separator in ["#", "/", ":"]:
    #     if separator in uri_str:
    #         return uri_str.split(separator)[-1]
    return uri_str


if __name__ == '__main__':
    # 读取RDF文件
    g = Graph()
    g.parse('./anime_datas/anime_graph.ttl', format='turtle')
    # 绘制图
    # visualize_graph(g)
    # exit(0)
    # print(g.all_nodes())

    # ps = set()
    # for s, p, o in g:
    #     print(unquote(str(s)), unquote(str(p)), unquote(str(o)))
    #     ps.add(unquote(str(p)))
    # print(ps)

    from urllib.parse import quote

    # SPARQL

    # SPARQL = f"""SELECT ?anime_name ?filter_cv
    # WHERE {{
    #     ?anime_name <anime://{quote('配音演员')}> ?anime_cv .
    #     FILTER(?anime_cv = ?filter_cv) .
    #     <anime://{quote('不想加班的公会柜台小姐决定单挑地城BOSS')}> <anime://{quote('配音演员')}> ?filter_cv .
    # }}
    # """

    SPARQL = f"""SELECT ?anime_name ?filter_cv
        WHERE {{
            ?anime_name <anime://配音演员> ?anime_cv.
            FILTER(?anime_cv = ?filter_cv).
            <anime://不想加班的公会柜台小姐决定单挑地城BOSS> <anime://配音演员> ?filter_cv.
        }}
    """

    #     SPARQL = """
    #     SELECT DISTINCT ?anime_name
    # WHERE {
    #     # 获取BanG Dream! Ave Mujica的导演
    #     <anime://BanG Dream! Ave Mujica> <anime://导演> ?director.
    #
    #     # 查询该导演参与制作的其他番剧
    #     ?anime_name <anime://导演> ?director.
    #
    #     # 排除BanG Dream! Ave Mujica本身
    #     FILTER(?anime_name != <anime://BanG Dream! Ave Mujica>)
    # }"""

    import re

    for uri_item in re.findall(r'<anime://(.*?)>', SPARQL, re.DOTALL):
        print(uri_item)
        SPARQL = SPARQL.replace(f'<anime://{uri_item}>', f'<anime://{quote(uri_item)}>')

    print(SPARQL)
    result = g.query(SPARQL)
    print(len(result))
    for row in result:
        print([unquote(str(item)) for item in row])
