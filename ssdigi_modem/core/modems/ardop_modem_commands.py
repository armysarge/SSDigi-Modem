"""
Enhanced ARDOP host commands generation for SSDigi Modem
"""

def generate_host_commands(config, bandwidth, callsign, grid_square):
    """
    Generate ARDOP HOST commands based on current settings

    Args:
        config: Configuration object
        bandwidth: Current bandwidth setting
        callsign: Current callsign
        grid_square: Current grid square

    Returns:
        str: Semicolon-separated string of commands to send to the ARDOP modem
    """
    commands = []

    # Add commands based on settings

    # Always include LISTEN command to start in receive mode
    commands.append("LISTEN")

    # Set ARQ bandwidth and enforcement mode
    if bandwidth:
        arqbw_mode = config.get('modem', 'arqbw_mode', 'MAX')
        commands.append(f"ARQBW {bandwidth}{arqbw_mode}")

    # Set Call Bandwidth if specified
    callbw = config.get('modem', 'callbw', 'UNDEFINED')
    if callbw != "UNDEFINED":
        commands.append(f"CALLBW {callbw}")

    # Set protocol mode (ARQ or FEC)
    protocol_mode = config.get('modem', 'protocol_mode', 'ARQ')
    commands.append(f"PROTOCOLMODE {protocol_mode}")

    # Set ARQ timeout
    arq_timeout = config.get('modem', 'arq_timeout', 120)
    commands.append(f"ARQTIMEOUT {arq_timeout}")

    # Set mycall
    if callsign:
        commands.append(f"MYCALL {callsign}")

    # Set grid square if available
    if grid_square:
        commands.append(f"GRIDSQUARE {grid_square}")

    # Set FEC mode
    if protocol_mode == "FEC":
        fec_mode = config.get('modem', 'fec_mode', '4FSK.500.100S')
        commands.append(f"FECMODE {fec_mode}")

        # Set FEC repeats
        fec_repeats = config.get('modem', 'fec_repeats', 0)
        commands.append(f"FECRPT {fec_repeats}")

        # Set FEC ID
        if config.get('modem', 'fec_id', False):
            commands.append("FECID TRUE")

    # Set leader and trailer lengths
    leader = config.get('modem', 'leader', 120)
    commands.append(f"LEADER {leader}")

    trailer = config.get('modem', 'trailer', 0)
    commands.append(f"TRAILER {trailer}")

    # Set squelch
    squelch = config.get('modem', 'squelch', 5)
    commands.append(f"SQUELCH {squelch}")

    # Set busy detection
    busydet = config.get('modem', 'busydet', 5)
    commands.append(f"BUSYDET {busydet}")

    # Set transmit level (0-100)
    tx_level = int(config.get('modem', 'tx_level', 0.9) * 100)
    commands.append(f"DRIVELEVEL {tx_level}")

    # Set tuning range
    tuning_range = config.get('modem', 'tuning_range', 100)
    commands.append(f"TUNINGRANGE {tuning_range}")

    # Set autobreak for ARQ flow control
    autobreak = "TRUE" if config.get('modem', 'autobreak', True) else "FALSE"
    commands.append(f"AUTOBREAK {autobreak}")

    # Set busy block
    busyblock = "TRUE" if config.get('modem', 'busyblock', False) else "FALSE"
    commands.append(f"BUSYBLOCK {busyblock}")

    # Set CW ID
    cwid = "TRUE" if config.get('modem', 'cwid', False) else "FALSE"
    commands.append(f"CWID {cwid}")

    # Set FSK only mode
    fskonly = "TRUE" if config.get('modem', 'fskonly', False) else "FALSE"
    commands.append(f"FSKONLY {fskonly}")

    # Set use of 600 baud modes
    use600 = "TRUE" if config.get('modem', 'use600modes', False) else "FALSE"
    commands.append(f"USE600MODES {use600}")

    # Set faststart mode
    faststart = "TRUE" if config.get('modem', 'faststart', True) else "FALSE"
    commands.append(f"FASTSTART {faststart}")

    # Set console log verbosity
    consolelog = config.get('modem', 'consolelog', 6)
    commands.append(f"CONSOLELOG {consolelog}")

    # Set extra RX/TX delay
    extradelay = config.get('modem', 'extradelay', 0)
    if extradelay > 0:
        commands.append(f"EXTRADELAY {extradelay}")

    # Set input noise (diagnostic feature)
    input_noise = config.get('modem', 'input_noise', 0)
    if input_noise > 0:
        commands.append(f"INPUTGAUSSIANNOISE {input_noise}")

    # Set command trace
    cmdtrace = "TRUE" if config.get('modem', 'cmd_trace', False) else "FALSE"
    commands.append(f"CMDTRACE {cmdtrace}")

    # Check for custom commands in config
    custom_commands = config.get('modem', 'custom_commands', '')
    if custom_commands:
        # Split by semicolon and add each command
        for cmd in custom_commands.split(';'):
            if cmd.strip():  # Only add non-empty commands
                commands.append(cmd.strip())

    # Join all commands with semicolons
    return ';'.join(commands)
