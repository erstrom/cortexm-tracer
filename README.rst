
Overview
========

The cortexm tracer is a tool that translates *PC* and *LR* register values into
a call graph. It uses the map file produced by the linker when mapping the
execution address (value of *PC* and *LR*) to a function name.

The tool can be used to debug execution flow of a program on an ARM Cortex-M
based microcontroller.

It is especially useful when a JTAG connection is not available or can't be
used (typically in code that involves enter/exit from Low power modes).

Function call tracing is an excellent way of getting to know a new code base.

In order to be able to trace the flow of execution in a program, the tracer
must continuously monitor the *PC* and *LR* registers of all functions that
is going to be traced.

Each function must save the current value of *PC* and *LR* in to a trace buffer
from where the tracer can collect the data.

From version 0.2 the tool has been extended to support a few additional features:

- Data hexdumps
- ASCII logs

Format of the trace data
========================

A typical Cortex-M based MCU has very little memory, so it is important to
keep the trace data as small as possible. As result of this, the tracer uses
binary data instead of ASCII.

Below is an outline of one chunk of function trace data::

    +----------+---------------+--------+--------+--------+
    | syncbits | flags present | invect |   PC   |   LR   |
    +----------+---------------+--------+--------+--------+
     6 bits     1 bit          9 bits   32 bits  32 bits

The sync bits are a sequence of bits (0b110000) that tells the tracer that
this is the start of a new trace chunk. The reason for having a sync sequence
is to let the tracer re-sync in case data gets corrupted or lost.

On a cortex-M MCU, the code memory is in the range [0 .. 0x1ffffff].
This means that the value of *PC* and *LR* should never start with the sync bit
sequence. Hence the likelihood for re-syncing on the wrong byte is minimal.

The intvect contains the interrupt vector number and is used by the tracer
to tell from which context the function was called from (which interrupt).

The value is derived from the VECTACTIVE field in the SCB ICSR register.
A value of zero means no interrupt context.

See ARM infocenter for more info about the ICSR register:

http://infocenter.arm.com/help/index.jsp?topic=/com.arm.doc.dui0552a/CIHFDJCA.html

*PC* and *LR* are written in big endian format (makes it easier to view hexdumps).

The *flags present* bit indicates that the trace chunk contains flags.
If set, the chunk will look like this::

    +----------+-------------------+-------+-----------------------------------+
    | syncbits | flags present (1) | flags | Different data depending on flags |
    +----------+-------------------+-------+-----------------------------------+
     6 bits     1 bit               8 bits  X bits

Currently, the below flags are supported::

    MORE_FLAGS = 1
    DATA_DUMP  = 2
    ASCII_LOG  = 4

In case *flags present* is not set, the data will always be interpreted as a
function trace chunk.

Special traces
==============

As mentioned before, the trace data will have a different interpretation depending
on the flags.

Data dump trace
---------------

Below is an outline of one chunk of data dump trace::

    +----------+-------------------+-----------+--------+-----------+----------+------+
    | syncbits | flags present (1) | flags (2) | unused | data addr | data len | data |
    +----------+-------------------+-----------+--------+-----------+----------+------+
     6 bits     1 bit               8 bits      1 bit    32 bits     16 bits

Example::

    +----------+---------------+----------+----+----------+-----+------+
    | syncbits | flags present | flags    | DC | addr     | len | data |
    +----------+---------------+----------+----+----------+-----+------+
    |  110000  | 1             | 00000001 | X  | 1000.... | ... | ...  |
    +----------+---------------+----------+----+----------+-----+------+
    Hex:
    |             C2              |     02     | 8....



ASCII log trace
---------------

Below is an outline of one chunk of ASCII log trace::

    +----------+-------------------+-----------+--------+---------+------------+
    | syncbits | flags present (1) | flags (4) | unused | log len | ASCII data |
    +----------+-------------------+-----------+--------+---------+------------+
     6 bits     1 bit               8 bits      1 bit    16 bits

Example (4 byte string)::

    +----------+---------------+----------+----+-------------------+------+
    | syncbits | flags present | flags    | DC | len               | data |
    +----------+---------------+----------+----+-------------------+------+
    |  110000  | 1             | 00000010 | X  | 00000000 00001000 | ...  |
    +----------+---------------+----------+----+-------------------+------+
    Hex:
    |             C2              |     04     |       00 04       | ...

Limitations/TODO
=================

The tool is currently in a beta state with a few features missing.

It currently only support parsing of IAR map files and has only been used
with an STM32F3 MCU.

The top items on the TODO list are:
- support for gcc map files
- support for other interrupt contexts than STM32F3

Target configuration
====================

The target MCU must generate the raw data and provide it to the tool
in some way.

The most common way to do this is to  transmit the data on a serial
interface (typically a UART).

The trace data must be collected for each function that is going to be
present in the trace.

In order to do so, a trace point must be added in each function (preferably
at the beginning of the function).

Below is a macro defining a tracepoint (IAR syntax)::

    #define TRACE_POINT \
    do { \
        register unsigned long pc, lr; \
        __asm("mov %0, PC" : "=r" (pc) : ); \
        __asm("mov %0, LR" : "=r" (lr) : ); \
        ftrace_trace(pc, lr); \
    } while(0)

The macro will read out the *PC* and *LR* registers and store them into
two c-variables. The variables will then be passed as arguments to the
tracing function that is responsible for writing the trace data to the
serial device.

The gcc equivalent will look like this::

    #define TRACE_POINT \
    do { \
        register unsigned long pc, lr; \
        asm("mov %0, %%pc;" : "=r" (pc) : ); \
        asm("mov %0, %%lr;" : "=r" (lr) : ); \
        ftrace_trace(pc, lr); \
    } while(0)

Below is an example of two functions where trace points have been added::

    void foo(void)
    {
        TRACE_POINT;
        int some_var;

        ...

        bar(some_var);

        ...
    }

    void bar(int some_var)
    {
        TRACE_POINT;
        ...
    }

The tracing function (``ftrace_trace`` in the above macro) does the
actual writing of the trace data to the trace buffer.
The most typical implementation is to write the trace data directly to
a UART (see below).

Each micro controller needs to define its own trace function.

Host configuration
==================

Tracing over UART
-----------------

Tracing over a UART is probably the most likely scenario when tracing.
The target device does not need to have an internal trace buffer and no
mechanism for reading trace data from the device is needed.

The trace analyzer just needs to listen for incoming data on the UART
and interpret the data on-the-fly.

Since the data transmitted from the device is binary, the UART must be
configured in raw mode.

This can be done with *stty* like this::

    stty -F /dev/ttyUSB0 raw

It is of course also important that the baudrate of the device and host
is configured in the same way::

    stty -F /dev/ttyUSB0 ispeed 460800

The above two examples assumes a USB serial device (e.g. an FTDI TTL-232R)
is used on the host.

The tracing script can be invoked like this::

    cat /dev/ttyUSB0 | cortexm_tracer -m /path/to/mapfile.map

The tracer will read data from the UART and write the trace to stdout
as soon as one full trace chunk has been received.

Below is a snippet showing how a trace can look like::

    main (0):          0.000221 foobar.bar <- foobar.foo
    main (0):          0.000165 foobar.foobar <- foobar.bar
    RTC_WKUP (19):     0.179189 RealTimeClock.RTC_WKUP_IRQHandler <- <unknown function>
    RTC_WKUP (19):     0.000252 RealTimeClock.HAL_RTCEx_WakeUpTimerEventCallback <- stm32f3xx_hal_rtc_ex.HAL_RTCEx_WakeUpTimerIRQHandler
    RTC_WKUP (19):     0.000102 foobar.wup_ev_handler <- RealTimeClock.HAL_RTCEx_WakeUpTimerEventCallback

The leftmost value is a string specifying the context in which the function
was called.

The actual interrupt number is also added next to the context name.

The context specifier is followed by a time stamp and a function call pair
in the form: ``objfile.to <- objfile.from``

In case the tracer can't find a function in the map file it will print
``<unknown function>``

The reason why the object name is prepended to the function name is to make
it easier to see which function is called in the case of static functions with
the same name (in different object files).

The time stamps are generated by the host tool, so if the raw data is saved to
a file (``cat /dev/ttyUSB0 > my-dump-file``) and analyzed afterwards
(``cortexm_tracer -m /path/to/mapfile.map -f my-dump-file``), the produced
time stamps will be invalid (probably very close to zero).
