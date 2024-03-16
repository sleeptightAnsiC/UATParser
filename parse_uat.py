##
# Please, have in mind that this was written as proof of concent
#   it is slow and overcomplicated, the goal was to write it ASAP
#
# Following script invokes UnrealAutomationTool twice
#   and parses the output so we can get every UAT command, help,
#   parameter, parameter's description and default arguments
# After parsing is done, the result is saved to 'out_commands' variable
##

# WARN: we are using ue4cli for getting the RunUAT script

import subprocess
import dataclasses
import pickle

# raw output of RunUAT -List
proc_list = subprocess.run(["ue4", "uat", "-List", "-utf8output"], capture_output=True, text=True)
assert proc_list.returncode == 0

# convert to: RunUAT Command1 -Help Command2 -Help ... CommandN -Help
proc_help_arguments = ["ue4", "uat", "-utf8output"]
DOUBLE_INDENT = "    "
for line in proc_list.stdout.split('\n'):
    double_indent_index = line.find(DOUBLE_INDENT)
    assert double_indent_index == -1 or double_indent_index == 0
    if double_indent_index == 0:
        proc_help_arguments += [line.replace(DOUBLE_INDENT, ''), "-Help"]

# raw output of: RunUAT Command1 -Help Command2 -Help ... CommandN -Help
proc_help = subprocess.run(proc_help_arguments, capture_output=True, text=True)
assert proc_help.returncode == 0

# remove unnecessary whitespaces from Help section
# this is slow but gonna help us with parsing a lot
proc_help_output = proc_help.stdout.replace("\n     ", ' ')
double_space = "  "
while proc_help_output.find(double_space) != -1:
    proc_help_output = proc_help_output.replace(double_space, ' ')
proc_help_output = proc_help_output.replace("\n -", "\n-")

# From now on we gonna parse proc_help_output
# proc_help_output generally has few repetitive things:
#
# - the very beggining of proc_help_output contains useless logging
# - name of the command with phrase " Help:"
# - the description of command starting after line with " Help:"
#       and ending before the line with "Parameters:"
#       but it also contains empty lines
# - parameters starting after line with "Parameters:"
#       and ending before the line with " Help:"
#       but also containing one empty line at the very end
#       Each parameter starts with "-" and ends before whitespace.
#       If a parameter contains "=", it means it has default/suggested value
#       Also some parameters display: "Duplicated help..." so we need to handle it
# - few last lines of proc_help_output contains useless logging
#
# parser below recognizes all of these stages
# it is VERY SLOW, but it works!

@dataclasses.dataclass
class UATParameter:
    name: str = ''
    description: str = ''
    default: str = ''

@dataclasses.dataclass
class UATCommand:
    name: str = ''
    help: str = ''
    parameters: [UATParameter] = dataclasses.field(default_factory=list)

# enumeration - shows where we are while parsing
STAGE_START = 0
STAGE_HELP = 1
STAGE_PARAMS = 2
STAGE_END = 3

# current state of parser
current_stage = STAGE_START
current_command: UATCommand or None = None
pendign_duplicates: {str: UATCommand} = {}

# result of parsing
out_commands: [UATCommand] = []

# PARRRRRSSSSSINGGGG...
# this is slow because we go line by line instead of character by character,
#   and then we are doing costly substring searches instead of tokenazing
#   but current aproach is just supper simple and quick to implement
for line in proc_help_output.split('\n'):
    if line == '':
        pass
    elif -1 != line.find(" Help:"):
        current_stage = STAGE_HELP
        if current_command:
            out_commands += [current_command]
        i_space = line.find(' ')
        assert i_space != -1
        name = line[:i_space]
        current_command = UATCommand(name=name)
    elif -1 != line.find("Parameters:"):
        current_stage = STAGE_PARAMS
    elif current_stage == STAGE_START or current_stage == STAGE_END:
        pass
    elif current_stage == STAGE_HELP:
        current_command.help += line + '\n'
    elif current_stage == STAGE_PARAMS:
        if -1 != line.find("Duplicated help parameter \""):
            i_dash = line.find('-')
            param_name = line[i_dash:-1]
            param = UATParameter(name=param_name)
            current_command.parameters += [param]
            pendign_duplicates[param_name] = param
        elif line[0] == '-':
            i_dash = 0
            i_equal = line.find('=')
            i_space = line.find(' ')
            if i_equal > i_space:
                i_equal = -1
            param_name = ''
            param_description = ''
            param_default = ''
            if i_equal != -1 and i_space != -1:
                param_name = line[i_dash:i_equal]
                param_description = line[i_space + 1:]
                param_default = line[i_equal + 1:i_space]
            elif i_equal != -1 and i_space == -1:
                param_name = line[i_dash:i_equal]
                param_default = line[i_equal + 1:]
            elif i_equal == -1 and i_space != -1:
                param_name = line[i_dash:i_space]
                param_description = line[i_space + 1:]
            elif i_equal == -1 and i_space == -1:
                param_name = line[i_dash:]
            else:
                assert False
            param = UATParameter(
                name=param_name,
                description=param_description,
                default=param_default,
            )
            current_command.parameters += [param]
            if param_name in pendign_duplicates.keys():
                pendign_duplicates[param_name].description = param_description
                pendign_duplicates[param_name].default = param_default
                pendign_duplicates.pop(param_name)
        else:
            current_stage = STAGE_END
    else:
        assert False

# out_commands contains parsed data

with open("./out.txt", "wb") as file:
    pickle.dump(out_commands, file)

with open("./out.txt", "rb") as file:
    out_commands = pickle.load(file)

print(out_commands)
