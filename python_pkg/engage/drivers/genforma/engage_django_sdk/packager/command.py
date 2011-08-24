"""Utilities for creating a command line processor.
   Copyright 2010 by genForma Corporation. Licensed under LGPL 3.
"""

from optparse import OptionParser
import sys
import os.path

class Command(object):
    """Base class for packager commands. Subclases should define the following class properties:
          NAME       - name of the command
          USAGE      - e.g. "%prog [options] foo arg1 arg2"
          SHORT_DESC - short (less than a line) description, printed by --help
          LONG_DESC  - longer description, printed by help command
          
    """
    def __init__(self, parser, args, options, num_additional_args=None):
        """Subclass constructors should call this one and then parse their arguments. If there
        is a problem, they should call parser.error(). We do a check here in the base
        case that the number of additional args is correct."""
        self.parser = parser
        self.args = args # the command has been stripped off the args array
        self.options = options
        # check number of additional ares if specified
        if (num_additional_args != None) and (len(args) != num_additional_args):
            parser.error("Expecting %d arguments for %s command." % (num_additional_args, self.get_name()))

    def get_name(self):
        return self.__class__.NAME

    def run(self):
        """Subclasses should implement this method. Returns an exit code
        """
        pass


class _CommandHelpCommand(Command):
    """Command to print help about other commands"""
    NAME = "help"
    USAGE = "%prog help command_name"
    SHORT_DESC = "Print more detailed help about a specific command"
    LONG_DESC = "Prints usage and description of specified command, then exits."
    def __init__(self, parser, args, options, num_additional_args=None):
        super(_CommandHelpCommand, self).__init__(parser, args, options, 1)
        self.commands = None # set by command manager
        self.requested_command = args[0]

    def set_commands(self, commands):
        self.commands = commands
        
    def run(self):
        if not self.commands.has_key(self.requested_command):
            sys.stderr.write("No command named '%s'\n" % self.requested_command)
            return 2
        command = self.commands[self.requested_command]
        usage = command.USAGE.replace("%prog", os.path.basename(sys.argv[0]))
        print "Usage:\n %s\n\n%s\n\n" % (usage, command.SHORT_DESC)
        print "%s\n" % command.LONG_DESC
        return 0
        


class CommandManager(object):
    def __init__(self):
        self.commands = {}
        self.command_names = []
        self.register_command(_CommandHelpCommand)

    def register_command(self, command):
        """command should be a subclass of Command whose constructor expects
           the following arguments: parser, args, options.
        """
        self.commands[command.NAME] = command
        self.command_names.append(command.NAME)

    def get_usage(self):
        cmd_str = "\n".join(["{cmd: <15} {desc}".format(cmd=self.commands[cn].NAME, desc=self.commands[cn].SHORT_DESC) for cn in self.command_names])
        return "%prog [options] COMMAND [ARGS]\n\nCOMMAND is one of:\n" + cmd_str + "\n"

    def add_options(self, parser):
        """This is for subclasses to add more options if desired.
        """
        pass

    def process_generic_options(self, options, args):
        """This is for subclasses to process any generic options before
        handing processing to the specified command.
        """
        pass
    
    def parse_command_args(self, argv):
        """Parse the command line arguments and instantiate the requested
        command.
        """
        parser = OptionParser(usage=self.get_usage())
        self.add_options(parser)
        (options, args) = parser.parse_args()
        self.process_generic_options(options, args)
        # determine the command, with error checking
        if len(args)<1:
            parser.error("First argument must be command, which is one of %s"
                         % ", ".join(self.command_names))
        command_name = args[0]
        if command_name not in self.command_names:
            parser.error("Command '%s' not valid, must be one of %s" %
                         (command_name, ", ".join(self.command_names)))
        command_constructor = self.commands[command_name]
        command = command_constructor(parser, args[1:], options)
        if command.get_name() == _CommandHelpCommand.NAME:
            # need a special case to pass the command map to the help command
            command.set_commands(self.commands)
        return command
