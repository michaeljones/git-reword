#!/usr/bin/env python3

from collections import defaultdict
import sys
import os

from pygit2 import Repository, discover_repository, GIT_SORT_TOPOLOGICAL


def first(iterable):

    for entry in iterable:
        return entry


class Node:

    def __init__(self, commit, children):

        self.commit = commit
        self.children = children
        self.overrides = {}

    @property
    def id(self):
        return self.commit.id

    @property
    def message(self):
        if 'message' in self.overrides:
            return self.overrides['message']

        return self.commit.message

    @message.setter
    def message(self, message):
        self.overrides['message'] = message

    def write(self, repo, node_lookup):

        def parent_id(id_):
            try:
                return node_lookup[id_].id
            except KeyError:
                return id_

        parents = list(map(parent_id, self.commit.parent_ids))

        oid = repo.create_commit(
            None,
            self.commit.author,
            self.commit.committer,
            self.message,
            self.commit.tree.id,
            parents
            )

        # Get new commit from the repo
        self.commit = repo.get(oid)


class Graph:

    def __init__(self, repo):
        self.repo = repo
        self.head_nodes = {}
        self.children = defaultdict(list)
        self.nodes = {}
        self.visited = []

    def walk(self, oid):

        walker = self.repo.walk(oid, GIT_SORT_TOPOLOGICAL)

        commit = first(walker)

        node = Node(commit, [])
        self.head_nodes[commit.id] = node

        # Record this node against its parents' ids as we can only find out parents not children so
        # we create a look up so that later we can find the children of a node in order to wire up
        # our custom node graph
        for entry in commit.parent_ids:
            self.children[entry].append(commit)

        self.visited.append(node)
        self.nodes[node.id] = node
        yield node

        for entry in walker:

            children = self.children[entry.id]
            node = Node(entry, children)

            self.visited.append(node)
            self.nodes[node.id] = node
            yield node

    def write(self):

        for node in reversed(self.visited):
            node.write(self.repo, self.nodes)

        return self.visited[0].id


def main(args):

    sha1 = args[0]

    # Discover the path to the repository we're in
    cwd = os.getcwd()
    repo_path = discover_repository(cwd)

    repository = Repository(repo_path)

    current_branch = repository.head

    old_commit = repository.revparse_single(sha1)

    latest_oid = current_branch.target
    latest_commit = repository.get(latest_oid)

    graph = Graph(repository)

    found = False
    for commit in graph.walk(repository.head.target):
        if commit.id == old_commit.id:
            found = True
            break

    if not found:
        return 1

    # Set the commit message
    commit.message = 'My new commit message'

    oid = graph.write()

    current_branch.target = oid

    # Add reflog entry for the change we've just made to the branch
    current_branch.log_append(oid, old_commit.author, "reword: message for %s" % sha1)

    head = repository.lookup_reference("HEAD")
    head.log_append(oid, old_commit.author,
                    "reword: switching to new %s" % current_branch.name)

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:])) 

