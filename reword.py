#!/usr/bin/env python3

from collections import defaultdict, OrderedDict

import sys
import os
import subprocess

from pygit2 import Repository, discover_repository, GIT_SORT_TOPOLOGICAL


def first(iterable):

    for entry in iterable:
        return entry


class ReferenceNode:

    def __init__(self, commit):
        self.commit = commit

    @property
    def id(self):
        return self.commit.id

    def changed(self):
        return False

    def written(self):
        return True


class Node:

    def __init__(self, commit, children):
        self.commit = commit
        self.children = children
        self.parents = []
        self.overrides = {}
        self._written = False

        self.parents = OrderedDict()
        for parent in commit.parents:
            self.parents[parent.id] = ReferenceNode(parent)

    def add_parent(self, parent):
        self.parents[parent.id] = parent

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
        if message != self.message:
            self.overrides['message'] = message

    def written(self):
        return self._written or not self.changed()

    def ready_to_write(self):
        return all(map(lambda p: p.written(), self.parents.values()))

    def changed(self):
        return self.overrides or any(map(lambda p: p.changed(), self.parents.values()))

    def write(self, repo):

        # Early exit if neither ourselves nor our parents have changed
        if not self.changed():
            return

        parents = list(map(lambda p: p.id, self.parents.values()))

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

        self._written = True


class CommitNotFoundError(Exception):
    pass


class Graph:

    def __init__(self, repo, start_oid=None):

        self.repo = repo
        self.head_nodes = {}
        self.children = defaultdict(list)
        self.nodes = {}
        self.visited = []
        self.last_node = None
        self.loose_ends = {}

        self.start_oid = start_oid
        if start_oid is None:
            self.start_oid = self.repo.head.target

    def get(self, oid):

        for commit in self.walk(self.start_oid):
            if commit.id == oid:
                return commit

        raise CommitNotFoundError()

    def walk(self, oid=None):

        if oid is None:
            oid = self.start_oid

        walker = self.repo.walk(oid, GIT_SORT_TOPOLOGICAL)

        commit = first(walker)

        node = Node(commit, [])
        self.head_nodes[commit.id] = node

        self.visited.append(node)
        self.nodes[node.id] = node
        self.last_node = node
        yield node

        # Record this node against its parents' ids as we can only find out parents not children so
        # we create a look up so that later we can find the children of a node in order to wire up
        # our custom node graph
        for entry in commit.parent_ids:
            self.children[entry].append(node)

        last_commit = commit

        for entry in walker:

            if entry.id not in set(last_commit.parent_ids):
                # If the new commit is not a parent of the last commit then we must have switched
                # over to another branch so we track the last commit as a loose end
                self.loose_ends[last_commit.id] = node

            # Check if our current commit is the parent of any of our loose ends
            cleanup = []
            for loose_end in self.loose_ends.values():
                if entry.id in set(p.id for p in loose_end.parents.values()):
                    cleanup.append(loose_end)

            for loose_end in cleanup:
                self.loose_ends.pop(loose_end.id)

            children = self.children[entry.id]
            node = Node(entry, children)

            for child in children:
                child.add_parent(node)

            # Store child relationships
            for id in entry.parent_ids:
                self.children[id].append(node)

            self.visited.append(node)
            self.nodes[node.id] = node
            self.last_node = node
            yield node

            last_commit = entry

    def write(self):

        stack = [self.last_node]
        stack.extend(self.loose_ends.values())

        last_written = None

        while stack:

            node = stack.pop()

            if not node.ready_to_write():
                stack.insert(0, node)
                continue

            node.write(self.repo)

            last_written = node

            for child in node.children:
                stack.append(child)

        return last_written.id


def get_new_commit_message(repo, commit_message):

    commit_message_filename = os.path.join(repo.path, 'COMMIT_EDITMSG')
    with open(commit_message_filename, 'w') as f:
        f.write(commit_message)

    editor = os.environ.get('EDITOR', 'vim')

    try:
        # We use a string and shell=True incase the editor value has spaces, ie. args of its own
        subprocess.check_call('%s %s' % (editor, commit_message_filename), shell=True)
    except subprocess.CalledProcessError:
        sys.stderr.write("Attempt to open text editor '%s' failed.\n" % editor)
        return 1

    new_commit_message = open(commit_message_filename).read()

    return new_commit_message


def main(args):

    sha1 = args[0]

    # Discover the path to the repository we're in
    cwd = os.getcwd()
    repo_path = discover_repository(cwd)

    repository = Repository(repo_path)

    current_branch = repository.head

    old_commit = repository.revparse_single(sha1)

    graph = Graph(repository)

    try:
        commit = graph.get(old_commit.id)
    except CommitNotFoundError:
        sys.stderr.write("Failed to find commit\n")
        return 1

    # Set the commit message
    commit.message = get_new_commit_message(repository, commit.message)

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

