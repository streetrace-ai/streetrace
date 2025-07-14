# Configure Command

The `streetrace configure` command allows you to manage StreetRace settings at both global and local scopes using TOML configuration files.

## Usage

### Show Configuration
```bash
# Show global configuration
streetrace configure --show --global

# Show local configuration  
streetrace configure --show --local
```

### Reset Configuration
```bash
# Reset global configuration
streetrace configure --reset --global

# Reset local configuration
streetrace configure --reset --local
```

### Interactive Configuration
```bash
# Interactive global configuration
streetrace configure --global

# Interactive local configuration
streetrace configure --local
```

## Configuration Files

- **Global**: `~/.streetrace/config.toml`
- **Local**: `./.streetrace/config.toml`

## Example Configuration

```toml
model = "anthropic/claude-3-5-sonnet-20241022"
```

## Interactive Menu

The interactive menu dynamically shows all available configuration parameters:

1. **Configure Model** - Set the default model
2. **Show All Settings** - Display current configuration
3. **Clear All Settings** - Remove all settings
4. **Save & Exit** - Save changes and exit
5. **Exit Without Saving** - Discard changes and exit

## Configuration Priority

When running StreetRace, configuration follows this priority:
1. Command line arguments
2. Local configuration (`./.streetrace/config.toml`)
3. Global configuration (`~/.streetrace/config.toml`)
4. Environment variables or defaults

## Extensibility

The configure system is designed to be extensible. New configuration parameters can be added by creating new `ConfigParameter` subclasses in the codebase.