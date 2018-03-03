import re
import sys
import bisect

# Example of IAR linker entry list 
#
# Entry                      Address    Size  Type      Object
# -----                      -------    ----  ----      ------
# .iar.init_table$$Base   0x0801ef4c           --   Gb  - Linker created -
# .iar.init_table$$Limit  0x0801ef70           --   Gb  - Linker created -
# ?main                   0x0801f045          Code  Gb  cmain.o [60]
# AHBPrescTable           0x0801f124    0x10  Data  Gb  system_stm32f3xx.o [5]
# APBPrescTable           0x0801f23c     0x8  Data  Gb  system_stm32f3xx.o [5]
# AddDataToChecksum       0x0801010f     0xc  Code  Lc  Settings.o [21]
# AddEventSubscriber      0x0801587f    0x32  Code  Lc  SMBus.o [51]
# AddLink                 0x0800cdcd   0x1de  Code  Lc  LinkManager.o [33]

# Long function names are split up in two lines:
# ICharger_IsChargingEnabled
#                         0x0801b1fd     0x8  Code  Gb  Charger.o [30]


iar_funcline_regex1 = "([a-zA-Z0-9_]+)(.*)"
iar_funcline_regex2 = "\s*0x([a-fA-F0-9]{8})\s+0x([a-fA-F0-9]+)\s+(\w+)"

iar_funcline_regex1_compiled = re.compile(iar_funcline_regex1)
iar_funcline_regex2_compiled = re.compile(iar_funcline_regex2)

class MapReaderIAR:

    def __init__(self, map_file):

        self.f = open(map_file, "r")
        self.__read_func_list()


    def __parse_line(self, line):

        if not self.part2:
            match = iar_funcline_regex1_compiled.match(line)
            if match is None:
                return None

            func_name = match.group(1)
            remainder = match.group(2)
            match = iar_funcline_regex2_compiled.match(remainder)
            if match is None and len(line.split(' ')) == 1:
                # This is a two-line entry
                return func_name
            elif match is None:
                return None
            addr = int(match.group(1), 16)
            size = int(match.group(2), 16)
            type_str = match.group(3)

            return (func_name, addr, size, type_str)

        else:
            match = iar_funcline_regex2_compiled.match(line)
            if match is None:
                # This is an invalid line
                return None
            addr = int(match.group(1), 16)
            size = int(match.group(2), 16)
            type_str = match.group(3)

            return (addr, size, type_str)


    def __read_func_list(self):

        for line in self.f:
            if "*** ENTRY LIST" in line:
                break;

        funcs = []
        self.part2 = False
        for line in self.f:
            parse_res = self.__parse_line(line)
            if parse_res is None:
                self.part2 = False
                continue
            elif not self.part2 and not isinstance(parse_res, tuple):
                func_name = parse_res
                self.part2 = True
                continue
            elif not self.part2 and len(parse_res) == 4:
                (func_name, addr, size, type_str) = parse_res
            elif self.part2 and len(parse_res) == 3:
                (addr, size, type_str) = parse_res
                self.part2 = False
            else:
                # Invalid result
                continue

            funcs.append({'addr':addr, 'name':func_name, 'type': type_str, 'size': size})

        # Sort the funcs list
        self.funcs = sorted(funcs, key=lambda k: k['addr'])


    def get_func_list(self):

        return self.funcs


    def find_func_from_addr(self, addr):

        keys = [func['addr'] for func in self.funcs]
        i = bisect.bisect_left(keys, addr)
        func = self.funcs[i - 1]
        return func

