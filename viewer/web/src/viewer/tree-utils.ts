export interface MetaObjectLite {
  id: string;
  name: string;
  type: string;
  parent: string | null;
}

export interface TreeNode {
  id: string;
  name: string;
  type: string;
  children: TreeNode[];
}

export function buildTree(objects: MetaObjectLite[]): TreeNode[] {
  const nodes = new Map<string, TreeNode>();
  for (const o of objects) {
    nodes.set(o.id, { id: o.id, name: o.name, type: o.type, children: [] });
  }
  const roots: TreeNode[] = [];
  for (const o of objects) {
    const node = nodes.get(o.id)!;
    const parent = o.parent ? nodes.get(o.parent) : undefined;
    if (parent) {
      parent.children.push(node);
    } else {
      roots.push(node);
    }
  }
  return roots;
}

export function typeCounts(objects: MetaObjectLite[]): [string, number][] {
  const counts = new Map<string, number>();
  for (const o of objects) {
    counts.set(o.type, (counts.get(o.type) ?? 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1]);
}

function nodeMatches(node: TreeNode, query: string, allowedTypes: ReadonlySet<string>): boolean {
  const q = query.trim().toLowerCase();
  const queryOk =
    q === "" ||
    node.name.toLowerCase().includes(q) ||
    node.type.toLowerCase().includes(q);
  const typeOk = allowedTypes.size === 0 || allowedTypes.has(node.type);
  return queryOk && typeOk;
}

export function filterTree(
  nodes: TreeNode[],
  query: string,
  allowedTypes: ReadonlySet<string>
): TreeNode[] {
  const out: TreeNode[] = [];
  for (const node of nodes) {
    const children = filterTree(node.children, query, allowedTypes);
    if (nodeMatches(node, query, allowedTypes) || children.length > 0) {
      out.push(children.length > 0 ? { ...node, children } : node);
    }
  }
  return out;
}
