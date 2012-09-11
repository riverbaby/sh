# -*- coding: utf8 -*-

import os
import unittest
import tempfile
import sys
import sh
import platform

IS_OSX = platform.system() == "Darwin"
IS_PY3 = sys.version_info[0] == 3
if IS_PY3:
    unicode = str
    python = sh.Command(sh.which("python%d.%d" % sys.version_info[:2]))
else:
    from sh import python


THIS_DIR = os.path.dirname(os.path.abspath(__file__))

skipUnless = getattr(unittest, "skipUnless", None)
if not skipUnless:
    def skipUnless(*args, **kwargs):
        def wrapper(thing): return thing
        return wrapper
        
requires_posix = skipUnless(os.name == "posix", "Requires POSIX")



def create_tmp_test(code):        
    py = tempfile.NamedTemporaryFile()
    if IS_PY3: code = bytes(code, "UTF-8")
    py.write(code)
    py.flush()
    # we don't explicitly close, because close will remove the file, and we
    # don't want that until the test case is done.  so we let the gc close it
    # when it goes out of scope
    return py



@requires_posix
class Basic(unittest.TestCase):
    
    def test_print_command(self):
        from sh import ls, which
        actual_location = which("ls")
        out = str(ls)
        self.assertEqual(out, actual_location)

    def test_unicode_arg(self):
        from sh import echo
        
        test = "漢字"
        if not IS_PY3: test = test.decode("utf8")
        
        p = echo(test).strip()
        self.assertEqual(test, p)
    
    def test_number_arg(self):
        from sh import python
        
        py = create_tmp_test("""
from optparse import OptionParser
parser = OptionParser()
options, args = parser.parse_args()
print(args[0])
""")
        
        out = python(py.name, 3).strip()
        self.assertEqual(out, "3")
        
    def test_exit_code(self):
        from sh import ls
        self.assertEqual(ls("/").exit_code, 0)
        
    def test_glob_warning(self):
        from sh import ls
        from glob import glob
        import warnings
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            ls(glob("ofjaoweijfaowe"))
            
            self.assertTrue(len(w) == 1)
            self.assertTrue(issubclass(w[-1].category, UserWarning))
            self.assertTrue("glob" in str(w[-1].message))
        
    def test_stdin_from_string(self):
        from sh import sed
        self.assertEqual(sed(_in="test", e="s/test/lol/").strip(), "lol")
        
    def test_ok_code(self):
        from sh import ls, ErrorReturnCode_2
        
        self.assertRaises(ErrorReturnCode_2, ls, "/aofwje/garogjao4a/eoan3on")
        ls("/aofwje/garogjao4a/eoan3on", _ok_code=2)
        ls("/aofwje/garogjao4a/eoan3on", _ok_code=[2])
    
    def test_quote_escaping(self):
        from sh import python
        
        py = create_tmp_test("""
from optparse import OptionParser
parser = OptionParser()
options, args = parser.parse_args()
print(args)
""")
        out = python(py.name, "one two three").strip()
        self.assertEqual(out, "['one two three']")
        
        out = python(py.name, "one \"two three").strip()
        self.assertEqual(out, "['one \"two three']")
        
        out = python(py.name, "one", "two three").strip()
        self.assertEqual(out, "['one', 'two three']")
        
        out = python(py.name, "one", "two \"haha\" three").strip()
        self.assertEqual(out, "['one', 'two \"haha\" three']")
        
        out = python(py.name, "one two's three").strip()
        self.assertEqual(out, "[\"one two's three\"]")
        
        out = python(py.name, 'one two\'s three').strip()
        self.assertEqual(out, "[\"one two's three\"]")
    
    def test_multiple_pipes(self):
        from sh import tr, python
        import time
        
        py = create_tmp_test("""
import sys
import os
import time

for l in "andrew":
    print(l)
    time.sleep(.2)
""")
        
        class Derp(object):
            def __init__(self):
                self.times = []
                self.stdout = []
                self.last_received = None
        
            def agg(self, line):
                self.stdout.append(line.strip())
                now = time.time()
                if self.last_received: self.times.append(now - self.last_received)
                self.last_received = now
        
        derp = Derp()
    
        # note that if we don't do _tty_out for the tr commands, they don't
        # write 
        p = tr(
               tr(
                  tr(
                     python(py.name, _piped=True),
                  "aw", "wa", _piped=True),
               "ne", "en", _piped=True),
            "dr", "rd", _out=derp.agg)
        
        p.wait()
        self.assertEqual("".join(derp.stdout), "werdna")
        self.assertTrue(all([t > .15 for t in derp.times]))
        
        
    def test_manual_stdin_string(self):
        from sh import tr
        
        out = tr("[:lower:]", "[:upper:]", _in="andrew").strip()
        self.assertEqual(out, "ANDREW")
        
        
    def test_manual_stdin_iterable(self):
        from sh import tr
        
        test = ["testing\n", "herp\n", "derp\n"]
        out = tr("[:lower:]", "[:upper:]", _in=test)
        
        match = "".join([t.upper() for t in test])
        self.assertEqual(out, match)
        
        
    def test_manual_stdin_file(self):
        from sh import tr
        import tempfile
        
        test_string = "testing\nherp\nderp\n"
        
        stdin = tempfile.NamedTemporaryFile()
        stdin.write(test_string.encode())
        stdin.flush()
        stdin.seek(0)
        
        out = tr("[:lower:]", "[:upper:]", _in=stdin)
        
        self.assertEqual(out, test_string.upper())
        
    
    def test_manual_stdin_queue(self):
        from sh import tr
        try: from Queue import Queue, Empty
        except ImportError: from queue import Queue, Empty
        
        test = ["testing\n", "herp\n", "derp\n"]
        
        q = Queue()
        for t in test: q.put(t)
        q.put(None) # EOF
        
        out = tr("[:lower:]", "[:upper:]", _in=q)
        
        match = "".join([t.upper() for t in test])
        self.assertEqual(out, match)
    
    
    def test_environment(self):
        from sh import python
        import os
        
        env = {"HERP": "DERP"}
        
        py = create_tmp_test("""
import os
try: del os.environ["__CF_USER_TEXT_ENCODING"] # osx adds this
except: pass
print(os.environ["HERP"] + " " + str(len(os.environ)))
""")
        out = python(py.name, _env=env).strip()
        self.assertEqual(out, "DERP 1")
    
        py = create_tmp_test("""
import os, sys
sys.path.insert(0, os.getcwd())
import sh
try: del os.environ["__CF_USER_TEXT_ENCODING"] # osx adds this
except: pass
print(sh.HERP + " " + str(len(os.environ)))
""")
        out = python(py.name, _env=env, _cwd=THIS_DIR).strip()
        self.assertEqual(out, "DERP 1")
        
    
    def test_which(self):
        from sh import which, ls
        self.assertEqual(which("fjoawjefojawe"), None)
        self.assertEqual(which("ls"), str(ls))
        
        
    def test_foreground(self):
        return
        raise NotImplementedError
    
    def test_no_arg(self):
        import pwd
        from sh import whoami
        u1 = whoami().strip()
        u2 = pwd.getpwuid(os.geteuid())[0]
        self.assertEqual(u1, u2)

    def test_incompatible_special_args(self):
        from sh import ls
        self.assertRaises(TypeError, ls, _iter=True, _piped=True)
            
            
    def test_exception(self):
        from sh import ls, ErrorReturnCode_2
        self.assertRaises(ErrorReturnCode_2, ls, "/aofwje/garogjao4a/eoan3on")
            
            
    def test_command_not_found(self):
        from sh import CommandNotFound
        
        def do_import(): from sh import aowjgoawjoeijaowjellll
        self.assertRaises(CommandNotFound, do_import)
            
            
    def test_command_wrapper_equivalence(self):
        from sh import Command, ls, which
        
        self.assertEqual(Command(which("ls")), ls) 
        
        
    def test_multiple_args_short_option(self):
        from sh import python
        
        py = create_tmp_test("""
from optparse import OptionParser
parser = OptionParser()
parser.add_option("-l", dest="long_option")
options, args = parser.parse_args()
print(len(options.long_option.split()))
""")
        num_args = int(python(py.name, l="one two three"))
        self.assertEqual(num_args, 3)
        
        num_args = int(python(py.name, "-l", "one's two's three's"))
        self.assertEqual(num_args, 3)
        
        
    def test_multiple_args_long_option(self):
        from sh import python
        
        py = create_tmp_test("""
from optparse import OptionParser
parser = OptionParser()
parser.add_option("-l", "--long-option", dest="long_option")
options, args = parser.parse_args()
print(len(options.long_option.split()))
""")
        num_args = int(python(py.name, long_option="one two three"))
        self.assertEqual(num_args, 3)
        
        num_args = int(python(py.name, "--long-option", "one's two's three's"))
        self.assertEqual(num_args, 3)
        
    
    def test_short_bool_option(self):
        from sh import id
        i1 = int(id(u=True))
        i2 = os.geteuid()
        self.assertEqual(i1, i2)

    
    def test_long_bool_option(self):
        from sh import id
        i1 = int(id(user=True, real=True))
        i2 = os.getuid()
        self.assertEqual(i1, i2)

    
    def test_composition(self):
        from sh import ls, wc
        c1 = int(wc(ls("-A1"), l=True))
        c2 = len(os.listdir("."))
        self.assertEqual(c1, c2)
        
    def test_incremental_composition(self):
        from sh import ls, wc
        c1 = int(wc(ls("-A1", _piped=True), l=True).strip())
        c2 = len(os.listdir("."))
        self.assertEqual(c1, c2)

    
    def test_short_option(self):
        from sh import sh
        s1 = sh(c="echo test").strip()
        s2 = "test"
        self.assertEqual(s1, s2)
        
    
    def test_long_option(self):
        from sh import sed, echo
        out = sed(echo("test"), expression="s/test/lol/").strip()
        self.assertEqual(out, "lol")
        
    
    def test_command_wrapper(self):
        from sh import Command, which
        
        ls = Command(which("ls"))
        wc = Command(which("wc"))
        
        c1 = int(wc(ls("-A1"), l=True))
        c2 = len(os.listdir("."))
        
        self.assertEqual(c1, c2)

    
    def test_background(self):
        from sh import sleep
        import time
        
        start = time.time()
        sleep_time = .5
        p = sleep(sleep_time, _bg=True)

        now = time.time()
        self.assertTrue(now - start < sleep_time)

        p.wait()
        now = time.time()
        self.assertTrue(now - start > sleep_time)
        
        
    def test_background_exception(self):
        from sh import ls, ErrorReturnCode_2
        p = ls("/ofawjeofj", _bg=True) # should not raise
        self.assertRaises(ErrorReturnCode_2, p.wait) # should raise
    
    def test_with_context(self):
        from sh import time, ls
        with time:
            out = ls().stderr
        self.assertTrue("pagefaults" in out)


    
    def test_with_context_args(self):
        from sh import time, ls
        with time(verbose=True, _with=True):
            out = ls().stderr
        self.assertTrue("Voluntary context switches" in out)


    
    def test_err_to_out(self):
        from sh import time, ls
        with time(_with=True):
            out = ls(_err_to_out=True)

        self.assertTrue("pagefaults" in out)


    
    def test_out_redirection(self):
        import tempfile
        from sh import ls

        file_obj = tempfile.TemporaryFile()
        out = ls(_out=file_obj)
        
        self.assertTrue(len(out) != 0)

        file_obj.seek(0)
        actual_out = file_obj.read()
        file_obj.close()

        self.assertTrue(len(actual_out) != 0)


    
    def test_err_redirection(self):
        import tempfile
        from sh import time, ls

        file_obj = tempfile.TemporaryFile()

        with time(_with=True):
            out = ls(_err=file_obj)
        
        file_obj.seek(0)
        actual_out = file_obj.read()
        file_obj.close()

        self.assertTrue(len(actual_out) != 0)

    
    def test_subcommand(self):
        from sh import time

        out = time.ls(_err_to_out=True)
        self.assertTrue("pagefaults" in out)

    
    def test_bake(self):
        from sh import time, ls
        timed = time.bake("--verbose", _err_to_out=True)
        out = timed.ls()
        self.assertTrue("Voluntary context switches" in out)
        
        
    def test_multiple_bakes(self):
        from sh import time
        timed = time.bake("--verbose", _err_to_out=True)
        out = timed.bake("ls")()
        self.assertTrue("Voluntary context switches" in out)


    def test_bake_args_come_first(self):
        from sh import ls
        ls = ls.bake(h=True)
        
        ran = ls("-la").ran
        ft = ran.index("-h")
        self.assertTrue("-la" in ran[ft:]) 

    
    def test_output_equivalence(self):
        from sh import whoami

        iam1 = whoami()
        iam2 = whoami()

        self.assertEqual(iam1, iam2)


    def test_stdout_callback(self):
        from sh import python
        
        py = create_tmp_test("""
import sys
import os

# unbuffered stdout
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

for i in range(5): print(i)
""")
        stdout = []
        def agg(line):
            stdout.append(line)
        
        p = python(py.name, _out=agg)
        p.wait()
        
        self.assertTrue(len(stdout) == 5)
        
        
        
    def test_stdout_callback_no_wait(self):
        from sh import python
        import time
        
        py = create_tmp_test("""
import sys
import os
import time

# unbuffered stdout
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

for i in range(5):
    print(i)
    time.sleep(.5)
""")
        
        stdout = []
        def agg(line): stdout.append(line)
        
        p = python(py.name, _out=agg)
        
        # we give a little pause to make sure that the NamedTemporaryFile
        # exists when the python process actually starts
        time.sleep(.5)
        
        self.assertTrue(len(stdout) != 5)
        
        
        
    def test_stdout_callback_line_buffered(self):
        from sh import python
        
        py = create_tmp_test("""
import sys
import os

# unbuffered stdout
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

for i in range(5): print("herpderp")
""")
        
        stdout = []
        def agg(line): stdout.append(line)
        
        p = python(py.name, _out=agg, _out_bufsize=1)
        p.wait()
        
        self.assertTrue(len(stdout) == 5)
        
        
        
    def test_stdout_callback_line_unbuffered(self):
        from sh import python
        
        py = create_tmp_test("""
import sys
import os

# unbuffered stdout
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

for i in range(5): print("herpderp")
""")
        
        stdout = []
        def agg(char): stdout.append(char)
        
        p = python(py.name, _out=agg, _out_bufsize=0)
        p.wait()
        
        # + 5 newlines
        self.assertTrue(len(stdout) == (len("herpderp") * 5 + 5))
        
        
    def test_stdout_callback_buffered(self):
        from sh import python
        
        py = create_tmp_test("""
import sys
import os

# unbuffered stdout
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

for i in range(5): sys.stdout.write("herpderp")
""")
        
        stdout = []
        def agg(chunk): stdout.append(chunk)
        
        p = python(py.name, _out=agg, _out_bufsize=4)
        p.wait()

        self.assertTrue(len(stdout) == (len("herp")/2 * 5))
        
        
        
    def test_stdout_callback_with_input(self):
        from sh import python
        
        py = create_tmp_test("""
import sys
import os

# unbuffered stdout
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

for i in range(5): print(i)
derp = raw_input("herp? ")
print(derp)
""")
        
        def agg(line, stdin):
            if line.strip() == "4": stdin.put("derp\n")
        
        p = python(py.name, _out=agg)
        p.wait()
        
        self.assertTrue("derp" in p)
        
        
        
    def test_stdout_callback_exit(self):
        from sh import python
        
        py = create_tmp_test("""
import sys
import os

# unbuffered stdout
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

for i in range(5): print(i)
""")
        
        stdout = []
        def agg(line):
            line = line.strip()
            stdout.append(line)
            if line == "2": return True
        
        p = python(py.name, _out=agg)
        p.wait()
        
        self.assertTrue("4" in p)
        self.assertTrue("4" not in stdout)
        
        
        
    def test_stdout_callback_terminate(self):
        import signal
        from sh import python
        
        py = create_tmp_test("""
import sys
import os
import time

# unbuffered stdout
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

for i in range(5): 
    print(i)
    time.sleep(.5)
""")
        
        stdout = []
        def agg(line, stdin, process):
            line = line.strip()
            stdout.append(line)
            if line == "3":
                process.terminate()
                return True
        
        p = python(py.name, _out=agg)
        p.wait()
        
        self.assertEqual(p.process.exit_code, -signal.SIGTERM)
        self.assertTrue("4" not in p)
        self.assertTrue("4" not in stdout)
        
        
        
    def test_stdout_callback_kill(self):
        from sh import python
        import signal
        
        py = create_tmp_test("""
import sys
import os
import time

# unbuffered stdout
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

for i in range(5): 
    print(i)
    time.sleep(.5)
""")
        
        stdout = []
        def agg(line, stdin, process):
            line = line.strip()
            stdout.append(line)
            if line == "3":
                process.kill()
                return True
        
        p = python(py.name, _out=agg)
        p.wait()
        
        self.assertEqual(p.process.exit_code, -signal.SIGKILL)
        self.assertTrue("4" not in p)
        self.assertTrue("4" not in stdout)
        
    def test_general_signal(self):
        import signal
        from signal import SIGINT
        
        py = create_tmp_test("""
import sys
import os
import time
import signal

def sig_handler(sig, frame):
    print(10)
    exit(0)
    
signal.signal(signal.SIGINT, sig_handler)

for i in range(5):
    print(i)
    sys.stdout.flush()
    time.sleep(0.5)
""")
        
        stdout = []
        def agg(line, stdin, process):
            line = line.strip()
            stdout.append(line)
            if line == "3":
                process.signal(SIGINT)
                return True
        
        p = python(py.name, _out=agg)
        p.wait()
        
        self.assertEqual(p.process.exit_code, 0)
        self.assertEqual(p, "0\n1\n2\n3\n10\n")
    
        
    def test_iter_generator(self):
        from sh import python
        
        py = create_tmp_test("""
import sys
import os
import time

for i in range(42): 
    print(i)
    sys.stdout.flush()
""")

        out = []
        for line in python(py.name, _iter=True):
            out.append(int(line.strip()))
        self.assertTrue(len(out) == 42 and sum(out) == 861)
        
       
    def test_nonblocking_iter(self):
        import tempfile
        from sh import tail
        from errno import EWOULDBLOCK
        
        tmp = tempfile.NamedTemporaryFile()
        for line in tail("-f", tmp.name, _iter_noblock=True): break
        self.assertEqual(line, EWOULDBLOCK)
        
        
    def test_for_generator_to_err(self):
        from sh import python
        
        py = create_tmp_test("""
import sys
import os

# unbuffered stdout
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 0)

for i in range(42): 
    sys.stderr.write(str(i)+"\\n")
""")

        out = []
        for line in python(py.name, _iter="err"): out.append(line)
        self.assertTrue(len(out) == 42)
        
        # verify that nothing is going to stdout
        out = []
        for line in python(py.name, _iter="out"): out.append(line)
        self.assertTrue(len(out) == 0)



    def test_piped_generator(self):
        from sh import python, tr
        from string import ascii_uppercase
        import time
        
        py1 = create_tmp_test("""
import sys
import os
import time

# unbuffered stdout
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

for letter in "andrew":
    time.sleep(0.5)
    print(letter)
        """)
        
        py2 = create_tmp_test("""
import sys
import os
import time

# unbuffered stdout
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

while True:
    line = sys.stdin.readline()
    if not line: break
    print(line.strip().upper())
        """)
        
        
        times = []
        last_received = None
        
        letters = ""
        for line in python(python(py1.name, _piped="out"), py2.name, _iter=True):
            if not letters: start = time.time()
            letters += line.strip()
            
            now = time.time()
            if last_received: times.append(now - last_received)
            last_received = now
        
        self.assertEqual("ANDREW", letters)
        self.assertTrue(all([t > .3 for t in times]))
        
        
    def test_generator_and_callback(self):
        from sh import python
        
        py = create_tmp_test("""
import sys
import os

# unbuffered stdout
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 0)

for i in range(42):
    sys.stderr.write(str(i * 2)+"\\n") 
    print(i)
""")
        
        stderr = []
        def agg(line): stderr.append(int(line.strip()))

        out = []
        for line in python(py.name, _iter=True, _err=agg): out.append(line)
        
        self.assertTrue(len(out) == 42)
        self.assertTrue(sum(stderr) == 1722)


    def test_bg_to_int(self):
        from sh import echo
        from os.path import realpath
        # bugs with background might cause the following error:
        #   ValueError: invalid literal for int() with base 10: ''
        self.assertEqual(int(echo("123", _bg=True)), 123)
        
        
    def test_cwd(self):
        from sh import pwd
        self.assertEqual(str(pwd(_cwd="/tmp")), realpath("/tmp")+"\n")
        self.assertEqual(str(pwd(_cwd="/etc")), realpath("/etc")+"\n")
        
        
    def test_huge_piped_data(self):
        from sh import tr
        
        stdin = tempfile.NamedTemporaryFile()
        
        data = "herpderp" * 1000 + "\n"
        stdin.write(data.encode())
        stdin.flush()
        stdin.seek(0)
        
        out = tr("[:lower:]", "[:upper:]", _in=data)
        self.assertEqual(len(out), len(data))


    def test_tty_input(self):
        from sh import python
        
        py = create_tmp_test("""
import sys
import os

if os.isatty(sys.stdin.fileno()):
    sys.stdout.write("password?\\n")
    sys.stdout.flush()
    pw = sys.stdin.readline().strip()
    sys.stdout.write("%s\\n" % ("*" * len(pw)))
else:
    sys.stdout.write("no tty attached!\\n")
""")

        test_pw = "test123"
        expected_stars = "*" * len(test_pw)
        d = {}

        def password_enterer(line, stdin):
            line = line.strip()
            if not line: return

            if line == "password?":
                stdin.put(test_pw+"\n")

            elif line.startswith("*"):
                d["stars"] = line
                return True

        pw_stars = python(py.name, _tty_in=True, _out=password_enterer)
        pw_stars.wait()
        self.assertEqual(d["stars"], expected_stars)

        response = python(py.name)
        self.assertEqual(response, "no tty attached!\n")


    def test_stringio_output(self):
        from sh import echo
        if IS_PY3:
            from io import StringIO
            from io import BytesIO as cStringIO
        else:
            from StringIO import StringIO
            from cStringIO import StringIO as cStringIO

        out = StringIO()
        echo("-n", "testing 123", _out=out)
        self.assertEqual(out.getvalue(), "testing 123")

        out = cStringIO()
        echo("-n", "testing 123", _out=out)
        self.assertEqual(out.getvalue().decode(), "testing 123")


    def test_stringio_input(self):
        from sh import cat
        
        if IS_PY3:
            from io import StringIO
            from io import BytesIO as cStringIO
        else:
            from StringIO import StringIO
            from cStringIO import StringIO as cStringIO
            
        input = StringIO()
        input.write("herpderp")
        input.seek(0)
        
        out = cat(_in=input)
        self.assertEqual(out, "herpderp")
        

    def test_internal_bufsize(self):
        from sh import cat
        
        output = cat(_in="a"*1000, _internal_bufsize=100, _out_bufsize=0)
        self.assertEqual(len(output), 100)
        
        output = cat(_in="a"*1000, _internal_bufsize=50, _out_bufsize=2)
        self.assertEqual(len(output), 100)
        
        
        


if __name__ == "__main__":
    if len(sys.argv) > 1:
        unittest.main()
    else:
        suite = unittest.TestLoader().loadTestsFromTestCase(Basic)
        unittest.TextTestRunner(verbosity=2).run(suite)
