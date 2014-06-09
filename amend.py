#!/usr/bin/env python3

import sys
import pygit2
import time

def ancestors(commit, repository):

    yield commit

    while True:
        if len(commit.parents) > 1:
            raise StopIteration()
        else:
            parent = commit.parents[0]
            yield parent
            commit = parent


def main(args):

    sha1 = args[0]

    repository = pygit2.Repository('example')

    current_branch = repository.head

    old_commit = repository.revparse_single(sha1)

    latest_oid = current_branch.target
    latest_commit = repository.get(latest_oid)

    history = []

    for commit in ancestors(latest_commit, repository):
        if commit.id == old_commit.id:
            break
        history.insert(0, commit)

    new_branch = current_branch.name + str(int(time.time()))

    commit = repository.create_commit(
        new_branch,
        old_commit.author,
        old_commit.committer,
        'my new commit message again',
        old_commit.tree.id,
        old_commit.parent_ids
        )

    prev_commit = commit
    for entry in history:
        prev_commit = repository.create_commit(
            new_branch,
            entry.author,
            entry.committer,
            entry.message,
            entry.tree.id,
            [prev_commit]
            )

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:])) 
