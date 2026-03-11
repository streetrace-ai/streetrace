#!/usr/bin/env python3
import sys
import json
import ast
from pathlib import Path
from typing import Any


def ast_to_data(node: Any) -> Any:
    """Convert an AST node to a JSON-serializable Python object."""
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.Dict):
        return {ast_to_data(k): ast_to_data(v) for k, v in zip(node.keys, node.values) if k is not None}
    elif isinstance(node, ast.List):
        return [ast_to_data(i) for i in node.elts]
    elif isinstance(node, ast.Tuple):
        return [ast_to_data(i) for i in node.elts]
    elif isinstance(node, ast.Name):
        if node.id == 'True': return True
        if node.id == 'False': return False
        if node.id == 'None': return None
        return node.id
    elif isinstance(node, ast.Call):
        res = {}
        class_name = ""
        if isinstance(node.func, ast.Name):
            class_name = node.func.id
        
        for keyword in node.keywords:
            if keyword.arg:
                res[keyword.arg] = ast_to_data(keyword.value)
        
        if node.args:
            args = [ast_to_data(a) for a in node.args]
            if class_name == "dict" and len(args) == 1 and isinstance(args[0], dict):
                args[0].update(res)
                return args[0]
            if class_name == "datetime":
                return "-".join(map(str, args))
            res["__args__"] = args
            
        if class_name and class_name[0].isupper() and not res.get("__args__"):
            return res
        return res if res else f"<{class_name}()>"
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        if isinstance(node.operand, ast.Constant):
            return -node.operand.value
    elif isinstance(node, ast.Expr):
        return ast_to_data(node.value)
    elif isinstance(node, ast.Module):
        if node.body:
            return ast_to_data(node.body[0])
    return str(node)


def parse_nested_json(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: parse_nested_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [parse_nested_json(i) for i in data]
    elif isinstance(data, str):
        stripped = data.strip()
        if (stripped.startswith("{") and stripped.endswith("}")) or \
           (stripped.startswith("[") and stripped.endswith("]")):
            try:
                parsed = json.loads(data)
                if isinstance(parsed, (dict, list)):
                    return parse_nested_json(parsed)
            except json.JSONDecodeError:
                pass
        if "\n" in data:
            return data.split("\n")
    return data


def find_balanced_literal(s: str) -> str:
    start_chars = "{[("
    start_idx = -1
    for i, char in enumerate(s):
        if char in start_chars:
            start_idx = i
            break
    if start_idx == -1: return s.strip()
    
    stack = []
    pairs = {'{': '}', '[': ']', '(': ')'}
    in_string = None
    i = start_idx
    while i < len(s):
        char = s[i]
        if in_string is None:
            if s[i:i+3] == "'''":
                in_string = "'''"
                i += 3
                continue
            if s[i:i+3] == '"""':
                in_string = '"""'
                i += 3
                continue
            if char in ("'", '"'):
                in_string = char
                i += 1
                continue
            if char in pairs:
                stack.append(pairs[char])
            elif char in pairs.values():
                if stack and stack[-1] == char:
                    stack.pop()
                    if not stack:
                        return s[start_idx : i + 1]
                else:
                    pass
        else:
            if char == '\\':
                i += 2
                continue
            if in_string in ("'''", '"""'):
                if s[i:i+3] == in_string:
                    in_string = None
                    i += 3
                    continue
            elif char == in_string:
                in_string = None
                i += 1
                continue
        i += 1
    return s[start_idx:].strip()


def main():
    if len(sys.argv) != 2:
        print("Usage: poetry run ./scripts/format.py FILE_NAME:LINE_NUMBER", file=sys.stderr)
        sys.exit(1)

    arg = sys.argv[1]
    file_path_str, line_num_str = arg.rsplit(":", 1)
    file_path = Path(file_path_str)
    line_num = int(line_num_str)

    with open(file_path, "r", encoding="utf-8") as f:
        target_line = None
        for i, line in enumerate(f, 1):
            if i == line_num:
                target_line = line
                break
        
        if not target_line:
            sys.exit(1)

        data_str = find_balanced_literal(target_line)

        try:
            tree = ast.parse(data_str)
            data = ast_to_data(tree)
        except SyntaxError:
            try:
                tree = ast.parse(f"dict({data_str})")
                data = ast_to_data(tree)
            except SyntaxError:
                tree = ast.parse(f"[{data_str}]")
                data = ast_to_data(tree)

        formatted_data = parse_nested_json(data)
        print(json.dumps(formatted_data, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
