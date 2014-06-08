#!/usr/bin/env python3

import sys
import pygit2

def main(args):

    repository = pygit2.Repository('example')

    old_commit = repository.revparse_single('HEAD')

    commit = repository.create_commit(
        'refs/heads/master', # the name of the reference to update
        old_commit.author,
        old_commit.committer,
        'my new commit message',
        old_commit.tree.id,
        old_commit.parent_ids
        )

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:])) 
