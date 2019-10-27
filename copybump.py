#! /usr/bin/env python3

import argparse
import datetime
import os
import re
import stat


FSF = 'by the Free Software Foundation, Inc.'
this_year = datetime.date.today().year
pyre_c = re.compile(r'# Copyright \(C\) ((?P<start>\d{4})-)?(?P<end>\d{4})')
pyre_n = re.compile(r'# Copyright ((?P<start>\d{4})-)?(?P<end>\d{4})')
new_c = '# Copyright (C) {}-{} {}'
new_n = '# Copyright {}-{} {}'

MODE = (stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
EXTENSIONS = [".py", ".js", ".rst"]
EXCLUDE_DIRS = [
    '.git', '.tox', '_build', 'example_project', '.sass-cache',
    'develop-eggs', 'eggs', 'parts', 'venv',
    ]


def remove(dirs, path):
    try:
        dirs.remove(path)
    except ValueError:
        pass


class CopyrightEditor:

    def __init__(self, new_template, owner):
        self.new_template = new_template
        self.owner = owner

    def do_file(self, path):
        permissions = os.stat(path).st_mode & MODE
        with open(path) as in_file, open(path + '.out', 'w') as out_file:
            try:
                for line in in_file:
                    mo_c = pyre_c.match(line)
                    mo_n = pyre_n.match(line)
                    if mo_c is None and mo_n is None:
                        out_file.write(line)
                        continue
                    mo = (mo_n if mo_c is None else mo_c)
                    start = (mo.group('end')
                             if mo.group('start') is None
                             else mo.group('start'))
                    if int(start) == this_year:
                        out_file.write(line)
                        continue
                    print(
                        self.new_template.format(start, this_year, self.owner),
                        file=out_file)
                    print('=>', path)
                    for line in in_file:
                        out_file.write(line)
            except UnicodeDecodeError:
                print('Cannot convert path:', path)
                os.remove(path + '.out')
                return
        os.rename(path + '.out', path)
        os.chmod(path, permissions)

    def do_walk(self, srcdir):
        for root, dirs, files in os.walk(srcdir):
            for excluded_dir in EXCLUDE_DIRS:
                if excluded_dir in dirs:
                    dirs.remove(excluded_dir)
            for filename in files:
                if os.path.splitext(filename)[1] not in EXTENSIONS:
                    continue
                path = os.path.join(root, filename)
                if os.path.isfile(path):
                    self.do_file(path)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "directories", nargs="+", help="directories with source files")
    parser.add_argument(
        "--owner", default="by the Free Software Foundation, Inc.")
    parser.add_argument("--noc", action="store_true", help="Don't use (C)")
    return parser.parse_args()


def main():
    args = parse_args()
    new_template = new_n if args.noc else new_c
    editor = CopyrightEditor(new_template=new_template, owner=args.owner)
    for srcdir in args.directories:
        editor.do_walk(srcdir)


if __name__ == '__main__':
    main()
