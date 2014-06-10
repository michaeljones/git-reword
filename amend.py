#!/usr/bin/env python3

import sys

from pygit2 import Repository, GIT_SORT_TOPOLOGICAL

def main(args):

    sha1 = args[0]

    repository = Repository('example')

    current_branch = repository.head

    old_commit = repository.revparse_single(sha1)

    latest_oid = current_branch.target
    latest_commit = repository.get(latest_oid)

    history = []

    for commit in repository.walk(repository.head.target, GIT_SORT_TOPOLOGICAL):
        if commit.id == old_commit.id:
            break
        history.insert(0, commit)

    commit = repository.create_commit(
        current_branch.name,
        old_commit.author,
        old_commit.committer,
        'my new commit message again',
        old_commit.tree.id,
        old_commit.parent_ids
        )

    prev_commit = commit
    for entry in history:
        prev_commit = repository.create_commit(
            current_branch.name,
            entry.author,
            entry.committer,
            entry.message,
            entry.tree.id,
            [prev_commit]
            )

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:])) 
