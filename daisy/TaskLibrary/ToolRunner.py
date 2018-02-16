import os
import glob
import shutil
import re

from .Runner import Runner
import daisy.Pipeline as P
import daisy.Experiment as E
import daisy.IOTools as IOTools
from daisy.Toolkit import as_namedtuple
from daisy.Pipeline.Execution import file_is_mounted, get_mounted_location


class ToolRunner(Runner):

    action = "tool"
    mountpoint = None

    def __call__(self, infiles, outfile, only_info=False):

        # NOTE: extras not implemented in ruffus 2.6.3, thus
        # use parameter:
        only_info = "only_info" in P.PARAMS

        if self.mountpoint:
            # revert mount redirection for arvados to allow redirection
            # on individual cluster nodes
            for d, key, value in IOTools.nested_iter(infiles):
                d[key] = re.sub(self.mountpoint, "arv=", value)

        self.instantiate_input(infiles)
        self.save_meta(outfile, output_file=outfile)

        if only_info:
            E.warn(
                "only_info - meta information has been updated")
            return

        params = self.build_params(output_file=outfile)
        benchmark = self.run(outfile, as_namedtuple(params))
        self.save_benchmark(outfile,
                            benchmark)

    def get_version(self):
        raise ValueError("no version defined for {}".format(self.name))


class run_tool_identity(ToolRunner):
    name = "identity"
    expected = ["file"]

    # override this in configuration file if not a .bam file.
    output = "result.bam"

    add_glob = None

    file = None

    def get_version(self):
        return "builtin"

    def run(self, outfile, params):

        if self.file is None:
            raise ValueError(
                "tool 'identity' requires a 'file'")

        fn = self.file
        if isinstance(fn, list):
            if len(fn) == 1:
                fn = fn[0]
            else:
                raise NotImplementedError(
                    "tool 'identity' called with multiple files: {}".format(
                        fn))

        source_fn = os.path.abspath(fn)

        def touch_and_mark_as_mounted(source, dest):
            o = os.stat(source)
            IOTools.touch_file(dest, times=(o.st_atime, o.st_mtime))
            with open(dest + ".mnt", "w") as outf:
                outf.write(get_mounted_location(source))

        if file_is_mounted(source_fn):
            link_f = touch_and_mark_as_mounted
        else:
            link_f = os.symlink

        if not os.path.exists(outfile):
            link_f(source_fn, outfile)

        if self.add_glob:
            prefix = len(os.path.basename(source_fn))
            for fn in glob.glob(source_fn + self.add_glob):
                target = outfile + os.path.basename(fn)[prefix:]
                if not os.path.exists(target):
                    link_f(os.path.abspath(fn), target)


class TestRunner(ToolRunner):
    expected = ["data"]
    output = "result.tsv"

    def get_version(self):
        return "builtin"

    def run(self, outfile, params):
        return P.run("{params.path} "
                     "{params.options} "
                     "{params.data} > {outfile}"
                     .format(**locals()))


class run_tool_modify(TestRunner):
    name = "modify"
    path = "daisy modify-string"


class run_tool_revert(TestRunner):
    name = "revert"
    path = "daisy revert-string"
