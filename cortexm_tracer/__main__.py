import sys
import os
import argparse
import struct
import datetime
from cortexm_tracer import MapReaderIAR
from cortexm_tracer import InterruptContext_STM32


STATE_READ_MAGIC = 0
STATE_READ_CONTEXT = 1
STATE_READ_PC = 2
STATE_READ_LR = 3

STATE_READ_CUSTOM_DATA_ADDR = 4
STATE_READ_CUSTOM_DATA_LEN = 5
STATE_READ_CUSTOM_DATA = 6

# Trace flags
TRACE_FLAG_CUSTOM_DATA = 1

# Trace types
TRACE_TYPE_FUNC = 0
TRACE_TYPE_CUSTOM_DATA = 1

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
    if cur_func:
        cur_func_name = cur_func['name']
    else:
        cur_func_name = "<unknown function>"
    prev_func = reader.find_func_from_addr(lr[0])
    if prev_func:
        prev_func_name = prev_func['name']
    else:
        prev_func_name = "<unknown function>"
    context_name = InterruptContext_STM32.getInterruptContext(context[0])
    context = "{} ({}):".format(context_name, context[0])
    print("{:15}   {:2}.{:06} {} <- {}".format(context, delta_time.seconds, delta_time.microseconds, cur_func_name, prev_func_name))
    sys.stdout.flush()

def _print_custom_data(custom_data_ba, custom_data_addr, data_len):

    print("Data dump: addr: 0x{:08x} len {} bytes".format(custom_data_addr, data_len))
    for idx, data in enumerate(custom_data_ba):
        print("  {:04}:  {:02x}".format(idx, data))

def _read_func_data(read_data):

    global state
    global pc_cnt
    global lr_cnt
    global pc
    global lr
    global context

    if state == STATE_READ_CONTEXT:
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

def _read_custom_data(read_data):

    global state
    global custom_data_len_cnt
    global custom_data_cnt
    global custom_data_addr_cnt
    global custom_data
    global custom_data_len
    global custom_data_addr
    global custom_data_addr_list

    if state == STATE_READ_CUSTOM_DATA_ADDR:
        custom_data_addr_list.append(read_data[0])
        custom_data_addr_cnt += 1
        if custom_data_addr_cnt == 4:
            custom_data_addr = custom_data_addr_list[0] << 24 | \
                               custom_data_addr_list[1] << 16 | \
                               custom_data_addr_list[2] << 8 | \
                               custom_data_addr_list[3]
            custom_data_addr_list = []
            custom_data_addr_cnt = 0
            custom_data_len_cnt = 0
            state = STATE_READ_CUSTOM_DATA_LEN
    elif state == STATE_READ_CUSTOM_DATA_LEN:
        if custom_data_len_cnt == 0:
            custom_data_len = read_data[0] << 8
            custom_data_len_cnt += 1
        elif custom_data_len_cnt == 1:
            custom_data_len |= read_data[0]
            state = STATE_READ_CUSTOM_DATA
            custom_data_cnt = 0
            custom_data_len_cnt = 0
            custom_data = bytearray()
    elif state == STATE_READ_CUSTOM_DATA:
        custom_data.extend(read_data)
        custom_data_cnt += 1
        if custom_data_cnt == custom_data_len:
            _print_custom_data(custom_data, custom_data_addr, custom_data_len)
            custom_data_cnt = 0
            custom_data_len_cnt = 0
            custom_data_addr_cnt = 0
            state = STATE_READ_MAGIC

def _read_data(f):

    global parsed_args
    global reader
    global prev_time
    global state
    global pc_cnt
    global lr_cnt
    global custom_data_len_cnt
    global custom_data_cnt
    global custom_data_addr_cnt
    global custom_data_addr_list

    try:
        read_data = ""
        pc_cnt = 0
        lr_cnt = 0
        resync_cnt = 0
        custom_data_len_cnt = 0
        custom_data_cnt = 0
        custom_data_addr_cnt = 0
        custom_data_addr_list = []
        state = STATE_READ_MAGIC
        prev_time = datetime.datetime.now()
        while True:
            read_data = f.read(1)
            if len(read_data) == 0:
                break

            if state == STATE_READ_MAGIC:
                read_data_magic = read_data[0] & 0xfc
                read_data_flags = (read_data[0] & ~0xfc) >> 1
                if read_data_magic == 0xc0:
                    if read_data_flags & TRACE_FLAG_CUSTOM_DATA:
                        trace_type = TRACE_TYPE_CUSTOM_DATA
                        state = STATE_READ_CUSTOM_DATA_ADDR
                    else:
                        trace_type = TRACE_TYPE_FUNC
                        state = STATE_READ_CONTEXT
                    if resync_cnt > 0:
                        print("*** Resync after {} bytes".format(resync_cnt))
                        resync_cnt = 0
                else:
                    if resync_cnt == 0:
                        print("*** WARNING ***")
                        print("*** Missing syncword!")
                    resync_cnt += 1
            else:
                if trace_type == TRACE_TYPE_FUNC:
                    _read_func_data(read_data)
                elif trace_type == TRACE_TYPE_CUSTOM_DATA:
                    _read_custom_data(read_data)
                else:
                    # Unknown trace type. Ignore
                    state == STATE_READ_MAGIC
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
