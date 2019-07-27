from pmutt import constants as c

def write_cti(filename, species, reactions, units):
    """
    
    https://cantera.org/tutorials/cti/cti-syntax.html#recognized-units
    """
    pass

def obj_to_CTI(obj, line_len=80, max_line_len=80, **kwargs):
    """Converts elementary data types to CTI format"""
    # See if the object has a specific format for CTI
    try:
        cti_str = obj.to_CTI(**kwargs)
    except AttributeError:
        if isinstance(obj, str):
            cti_str = obj
        elif isinstance(obj, (list, tuple, set)):
            cti_str = ' '.join(obj)
        elif isinstance(obj, dict):
            obj_list = ['{}:{}'.format(key, val) for key, val in obj.items()]
            cti_str = ' '.join(obj_list)
        elif obj is None:
            cti_str = ''
        else:
            cti_str = str(obj)

        # Fit on single line if output string is less than line_len
        cti_str_len = len(cti_str)
        if cti_str_len < (line_len - 2):
            cti_str = '"{}"'.format(cti_str)
        else:
            header_spaces = ' '*(max_line_len - line_len + 3)

            # Split string to be reassembled on multiple lines
            cti_list = cti_str.split(' ')
            cti_list.append('"""')
            cti_lines = ['"""']
            for i, cti_val in enumerate(cti_list):
                # The first line is limited to fewer characters
                if len(cti_lines) == 1:
                    line_limit = line_len
                else:
                    line_limit = max_line_len

                # If it is the first entry, do not insert a space
                if i == 0:
                    cti_lines[-1] = '{}{}'.format(cti_lines[-1], cti_val)
                # If the entry can fit on the same line, insert it
                elif (len(cti_lines[-1]) + len(cti_val) + 1) <= line_limit:
                    cti_lines[-1] = '{} {}'.format(cti_lines[-1], cti_val)
                # If the entry cannot fit on the same line, create a new line
                else:
                    cti_lines.append('{}{}'.format(header_spaces, cti_val))
            cti_str = '\n'.join(cti_lines)
    return cti_str