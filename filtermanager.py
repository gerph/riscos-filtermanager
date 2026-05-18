"""
FilterManager PyModule implementation.

This mirrors the existing C module's registry behaviour. It tracks filter
registrations and supports the same SWIs and *Filters command, but it does not
attempt to execute the registered callback addresses.
"""

from riscos.modules.pymodules import PyModule

import riscos.constants.services as services


class FilterEntry(object):

    def __init__(self, name, routine, r12, task_handle=None, event_mask=None,
                 border_mask=None, name_ptr=None):
        self.name = name
        self.routine = routine
        self.r12 = r12
        self.task_handle = task_handle
        self.event_mask = event_mask
        self.border_mask = border_mask
        self.name_ptr = name_ptr


class FilterManager(PyModule):
    version = '0.01'
    date = '18 May 2026'
    swi_base = 0x42640
    swi_prefix = "Filter"
    swi_names = [
            "RegisterPreFilter",
            "RegisterPostFilter",
            "DeRegisterPreFilter",
            "DeRegisterPostFilter",
            "RegisterRectFilter",
            "DeRegisterRectFilter",
            "RegisterCopyFilter",
            "DeRegisterCopyFilter",
            "RegisterPostRectFilter",
            "DeRegisterPostRectFilter",
            "RegisterPostIconFilter",
            "DeRegisterPostIconFilter",
            "RegisterIconBorderFilter",
            "DeRegisterIconBorderFilter",
        ]
    error_base = 0x81d400
    errors = [
            ('Err_FilterAlreadyRegistered', "Filter already registered"),
            ('Err_FilterNotRegistered', "Filter not registered"),
            ('Err_NoMoreRoomForFilters', "No more room for filters"),
            ('Err_InvalidParameters', "Invalid parameters"),
        ]
    commands = [
            ('Filters',
             '*Filters lists the registered filters.',
             0x00000000,
             'Syntax: *Filters'),
        ]
    entrypoint_names = [
            'callback_announce',
        ]

    def __init__(self, ro, module):
        super(FilterManager, self).__init__(ro, module)

        self.swi_dispatch = {
                0: self.swi_registerprefilter,
                1: self.swi_registerpostfilter,
                2: self.swi_deregisterprefilter,
                3: self.swi_deregisterpostfilter,
                4: self.swi_registerrectfilter,
                5: self.swi_deregisterrectfilter,
                6: self.swi_registercopyfilter,
                7: self.swi_deregistercopyfilter,
                8: self.swi_registerpostrectfilter,
                9: self.swi_deregisterpostrectfilter,
                10: self.swi_registerposticonfilter,
                11: self.swi_deregisterposticonfilter,
                12: self.swi_registericonborderfilter,
                13: self.swi_deregistericonborderfilter,
            }

        self.pre_filters = []
        self.post_filters = []
        self.rect_filters = []
        self.copy_filters = []
        self.post_rect_filters = []
        self.post_icon_filters = []
        self.icon_border_filters = []

        self.debug_filtermanager = False
        self.callback_pending = False
        self.ro.debug_register_ivar('filtermanager', self)

    def initialise(self, arguments, pwp):
        super(FilterManager, self).initialise(arguments, pwp)
        if self.debug_filtermanager:
            print("Module FilterManager initialised")
        func = self.module.entrypoints['callback_announce'].address
        self.ro.kernel.api.os_addcallback(func, self.pwp)
        self.callback_pending = True

    def finalise(self, pwp):
        if self.debug_filtermanager:
            print("Module FilterManager dying")
        if self.callback_pending:
            self.callback_pending = False
            func = self.module.entrypoints['callback_announce'].address
            self.ro.kernel.api.os_removecallback(func, self.pwp)
        self._announce(services.Service_FilterManagerDying)
        self._cleanup()
        super(FilterManager, self).finalise(pwp)

    def service(self, service, regs):
        if service == services.Service_WimpCloseDown:
            task_handle = regs[2]
            if self.debug_filtermanager:
                print("WimpCloseDown for task %08X" % (self._u32(task_handle),))
            if task_handle != 0:
                self.pre_filters = [entry for entry in self.pre_filters
                                    if entry.task_handle != task_handle]
                self.post_filters = [entry for entry in self.post_filters
                                     if entry.task_handle != task_handle]
                self.rect_filters = [entry for entry in self.rect_filters
                                     if entry.task_handle != task_handle]
                self.post_rect_filters = [entry for entry in self.post_rect_filters
                                          if entry.task_handle != task_handle]
                self.post_icon_filters = [entry for entry in self.post_icon_filters
                                          if entry.task_handle != task_handle]

    def swi(self, offset, regs):
        func = self.swi_dispatch.get(offset, None)
        if func:
            return func(regs)
        return False

    def cmd_filters(self, args):
        if args.strip():
            return False
        self._list_filters()
        return True

    def swi_registerprefilter(self, regs):
        return self._register_by_name_task(self.pre_filters,
                                           regs[0],
                                           regs[1], regs[2], regs[3])

    def swi_registerpostfilter(self, regs):
        return self._register_by_name_task(self.post_filters,
                                           regs[0],
                                           regs[1], regs[2], regs[3],
                                           event_mask=regs[4])

    def swi_deregisterprefilter(self, regs):
        return self._deregister_by_fields(self.pre_filters,
                                          regs[0],
                                          regs[1], regs[2], regs[3])

    def swi_deregisterpostfilter(self, regs):
        return self._deregister_by_fields(self.post_filters,
                                          regs[0],
                                          regs[1], regs[2], regs[3],
                                          event_mask=regs[4])

    def swi_registerrectfilter(self, regs):
        return self._register_by_name_task(self.rect_filters,
                                           regs[0],
                                           regs[1], regs[2], regs[3])

    def swi_deregisterrectfilter(self, regs):
        return self._deregister_by_fields(self.rect_filters,
                                          regs[0],
                                          regs[1], regs[2], regs[3])

    def swi_registercopyfilter(self, regs):
        name_ptr = regs[0]
        self._ensure_unique_name(self.copy_filters, name_ptr)
        self.copy_filters.insert(0, FilterEntry(self._read_string(name_ptr),
                                                regs[1], regs[2],
                                                name_ptr=name_ptr))
        return True

    def swi_deregistercopyfilter(self, regs):
        return self._deregister_by_fields(self.copy_filters,
                                          regs[0],
                                          regs[1], regs[2])

    def swi_registerpostrectfilter(self, regs):
        return self._register_by_name_task(self.post_rect_filters,
                                           regs[0],
                                           regs[1], regs[2], regs[3])

    def swi_deregisterpostrectfilter(self, regs):
        return self._deregister_by_fields(self.post_rect_filters,
                                          regs[0],
                                          regs[1], regs[2], regs[3])

    def swi_registerposticonfilter(self, regs):
        return self._register_by_name_task(self.post_icon_filters,
                                           regs[0],
                                           regs[1], regs[2], regs[3])

    def swi_deregisterposticonfilter(self, regs):
        return self._deregister_by_fields(self.post_icon_filters,
                                          regs[0],
                                          regs[1], regs[2], regs[3])

    def swi_registericonborderfilter(self, regs):
        name_ptr = regs[0]
        name = self._read_string(name_ptr)
        routine = regs[1]
        r12 = regs[2]
        border_mask = regs[3]
        entry = FilterEntry(name, routine, r12, border_mask=border_mask,
                            name_ptr=name_ptr)

        for current in self.icon_border_filters:
            if (current.name_ptr == entry.name_ptr and
                    current.routine == entry.routine and
                    current.r12 == entry.r12):
                raise self.error('Err_FilterAlreadyRegistered')

        self.icon_border_filters.insert(0, entry)
        return True

    def swi_deregistericonborderfilter(self, regs):
        name_ptr = regs[0]
        routine = regs[1]
        r12 = regs[2]
        index = 0

        while index < len(self.icon_border_filters):
            entry = self.icon_border_filters[index]
            if (entry.name_ptr == name_ptr and
                    entry.routine == routine and
                    entry.r12 == r12):
                del self.icon_border_filters[index]
                return True
            index += 1

        raise self.error('Err_FilterNotRegistered')

    def callback_announce(self, regs):
        self.callback_pending = False
        self._announce(services.Service_FilterManagerInstalled)

    def _announce(self, service_number):
        if hasattr(self.ro, 'services'):
            self.ro.services.dispatch(service_number, preserve=True)

    def _cleanup(self):
        self.pre_filters = []
        self.post_filters = []
        self.rect_filters = []
        self.copy_filters = []
        self.post_rect_filters = []
        self.post_icon_filters = []
        self.icon_border_filters = []

    def _read_string(self, addr):
        return self.ro.memory[addr].string

    def _register_by_name_task(self, filters, name_ptr, routine, r12, task_handle,
                               event_mask=None):
        self._ensure_unique_name_task(filters, name_ptr, task_handle)
        filters.insert(0, FilterEntry(self._read_string(name_ptr), routine, r12,
                                      task_handle=task_handle,
                                      event_mask=event_mask,
                                      name_ptr=name_ptr))
        return True

    def _ensure_unique_name_task(self, filters, name_ptr, task_handle):
        for entry in filters:
            if entry.name_ptr == name_ptr and entry.task_handle == task_handle:
                raise self.error('Err_FilterAlreadyRegistered')

    def _ensure_unique_name(self, filters, name_ptr):
        for entry in filters:
            if entry.name_ptr == name_ptr:
                raise self.error('Err_FilterAlreadyRegistered')

    def _deregister_by_fields(self, filters, name_ptr, routine, r12,
                              task_handle=None, event_mask=None):
        index = 0

        while index < len(filters):
            entry = filters[index]
            if (entry.name_ptr == name_ptr and
                    entry.routine == routine and
                    entry.r12 == r12 and
                    entry.task_handle == task_handle and
                    entry.event_mask == event_mask):
                del filters[index]
                return True
            index += 1

        raise self.error('Err_FilterNotRegistered')

    def _list_filters(self):
        self._write_table("Pre-filters:",
                          ("Name", "Routine", "R12", "Task"),
                          self.pre_filters,
                          lambda entry: (entry.name,
                                         self._hex(entry.routine),
                                         self._hex(entry.r12),
                                         self._hex(entry.task_handle)))

        self._write_table("Post-filters:",
                          ("Name", "Routine", "R12", "Task", "Mask"),
                          self.post_filters,
                          lambda entry: (entry.name,
                                         self._hex(entry.routine),
                                         self._hex(entry.r12),
                                         self._hex(entry.task_handle),
                                         self._hex(entry.event_mask)))

        self._write_table("Get Rectangle filters:",
                          ("Name", "Routine", "R12", "Task"),
                          self.rect_filters,
                          lambda entry: (entry.name,
                                         self._hex(entry.routine),
                                         self._hex(entry.r12),
                                         self._hex(entry.task_handle)))

        self._write_table("Rectangle Copy filters:",
                          ("Name", "Routine", "R12"),
                          self.copy_filters,
                          lambda entry: (entry.name,
                                         self._hex(entry.routine),
                                         self._hex(entry.r12)))

        self._write_table("Post-Rectangle filters:",
                          ("Name", "Routine", "R12", "Task"),
                          self.post_rect_filters,
                          lambda entry: (entry.name,
                                         self._hex(entry.routine),
                                         self._hex(entry.r12),
                                         self._hex(entry.task_handle)))

        self._write_table("Post-Icon filters:",
                          ("Name", "Routine", "R12", "Task"),
                          self.post_icon_filters,
                          lambda entry: (entry.name,
                                         self._hex(entry.routine),
                                         self._hex(entry.r12),
                                         self._hex(entry.task_handle)))

        self._write_table("Icon Border filters:",
                          ("Name", "Routine", "R12", "Mask"),
                          self.icon_border_filters,
                          lambda entry: (entry.name,
                                         self._hex(entry.routine),
                                         self._hex(entry.r12),
                                         self._hex(entry.border_mask)))

    def _write_table(self, heading, columns, rows, formatter):
        self.ro.kernel.writeln(heading)
        if not rows:
            self.ro.kernel.writeln("  None")
            self.ro.kernel.writeln("")
            return

        widths = [20]
        index = 1
        while index < len(columns):
            widths.append(8)
            index += 1

        self.ro.kernel.writeln(self._format_row(columns, widths))
        for entry in rows:
            self.ro.kernel.writeln(self._format_row(formatter(entry), widths))
        self.ro.kernel.writeln("")

    def _format_row(self, values, widths):
        parts = []
        index = 0

        while index < len(values):
            value = values[index]
            if value is None:
                value = ''
            parts.append(str(value).ljust(widths[index]))
            index += 1
        return "  " + " ".join(parts)

    def _hex(self, value):
        return "%08X" % (self._u32(value),)

    def _u32(self, value):
        return value & 0xffffffff
