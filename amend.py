#!/usr/bin/env python3

import sys
import os

from pygit2 import Repository, discover_repository, GIT_SORT_TOPOLOGICAL

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

    history = []

    found = False
    for commit in repository.walk(repository.head.target, GIT_SORT_TOPOLOGICAL):
        if commit.id == old_commit.id:
            found = True
            break
        history.insert(0, commit)

    if not found:
        return 1

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

    # Add reflog entry for the change we've just made to the branch
    current_branch.log_append(prev_commit, old_commit.author, "reword: message for %s" % sha1)

    head = repository.lookup_reference("HEAD")
    head.log_append(prev_commit, old_commit.author,
                    "reword: switching to new %s" % current_branch.name)

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:])) 
