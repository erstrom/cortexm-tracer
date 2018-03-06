import sys
import os
import argparse
import struct
import datetime
from cortexm_tracer import MapReaderIAR


STATE_READ_MAGIC = 0
STATE_READ_CONTEXT = 1
STATE_READ_PC = 2
STATE_READ_LR = 3

def _print_data(context_ba, pc_ba, lr_ba):

    global reader
    global prev_time

    cur_time = datetime.datetime.now()
    delta_time = cur_time - prev_time
    prev_time = cur_time
    context = struct.unpack(">B", context_ba)
    pc = struct.unpack(">L", pc_ba)
    lr = struct.unpack(">L", lr_ba)
    cur_func = reader.find_func_from_addr(pc[0])
    prev_func = reader.find_func_from_addr(lr[0])
    print("Context: {:2}    {:2}.{:06} {} <- {}".format(context[0], delta_time.seconds, delta_time.microseconds, cur_func['name'], prev_func['name']))
    sys.stdout.flush()

def _read_data(f):

    global parsed_args
    global reader
    global prev_time

    try:
        read_data = ""
        pc_cnt = 0
        lr_cnt = 0
        state = STATE_READ_MAGIC
        prev_time = datetime.datetime.now()
        while True:
            read_data = f.read(1)

            if state == STATE_READ_MAGIC:
                if read_data == b'\xc0':
                    state = STATE_READ_CONTEXT
            elif state == STATE_READ_CONTEXT:
                context = read_data
                state = STATE_READ_PC
                pc = bytearray()
            elif state == STATE_READ_PC:
                pc.extend(read_data)
                pc_cnt += 1
                if pc_cnt == 4:
                    state = STATE_READ_LR
                    lr = bytearray()
            elif state == STATE_READ_LR:
                lr.extend(read_data)
                lr_cnt += 1
                if lr_cnt == 4:
                    _print_data(context, pc, lr)
                    pc_cnt = 0
                    lr_cnt = 0
                    state = STATE_READ_MAGIC
    except KeyboardInterrupt:
        sys.stdout.flush()
        sys.stderr.flush()

def _load_options():

    global parsed_args
    parser = argparse.ArgumentParser(prog="cortexm_tracer",
                                     description="",
                                     formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-f', '--file', nargs=1, type=str,
                        help="Binary input file.\n"
                             "The file the data will be read from.\n"
                             "If omitted, data will be read from stdin.")
    parser.add_argument('-m', '--map-file', nargs=1, type=str,
                        help="Map file.\n"
                             "Linker map.")
    parsed_args = parser.parse_args()



def main():

    global parsed_args
    global reader

    _load_options()
    if parsed_args.file is None:
        sys.stderr.write('Missing input file. Reading stdin\n')
        f = sys.stdin
        # reopen stdin in binary mode
        f = os.fdopen(f.fileno(), 'rb', 0)
    else:
        f = open(parsed_args.file[0], "rb")
    if parsed_args.map_file is None:
        sys.stderr.write('Missing linker map file!\n')
        return

    reader = MapReaderIAR(parsed_args.map_file[0])
    _read_data(f)

if __name__ == "__main__":
    main()
