from typing import TypeVar, Dict, Optional, Any, cast
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class PromptConfig:
    """Configuration for user prompts."""
    prompt: str
    valid_options: Dict[str, T]
    default: str
    case_sensitive: bool = False
    max_attempts: int = 3
    error_message: Optional[str] = None


def get_user_confirmation(
        prompt: str,
        default: str,
        valid_options: Dict[str, T],
        case_sensitive: bool = False,
        max_attempts: int = 3
) -> Optional[T]:
    """
    Prompt user for input with validation and return typed response.

    Args:
        prompt: The prompt text to display to the user
        default: Default option if user enters empty input
        valid_options: Dictionary mapping valid input strings to their corresponding values
        case_sensitive: Whether to treat input case-sensitively
        max_attempts: Maximum number of invalid attempts before returning None

    Returns:
        Optional[T]: The corresponding value from valid_options if input is valid,
                    the default value if input is empty, or None if max attempts exceeded

    Examples:
        >>> options = {'y': True, 'n': False}
        >>> result = get_user_confirmation("Proceed?", "y", options)
        Proceed? [y/n, default: y]:
    """
    if not valid_options:
        raise ValueError("valid_options dictionary cannot be empty")
    if default not in valid_options:
        raise ValueError(f"default value '{default}' must be one of: {', '.join(valid_options.keys())}")

    config = PromptConfig(
        prompt=prompt,
        valid_options=valid_options,
        default=default,
        case_sensitive=case_sensitive,
        max_attempts=max_attempts
    )

    return _get_validated_input(config)


def _get_validated_input(config: PromptConfig) -> Optional[T]:
    """Internal function to handle input validation and processing."""
    options_display = '/'.join(config.valid_options.keys())
    full_prompt = f"{config.prompt} [{options_display}, default: {config.default}]: "

    attempts = 0
    while attempts < config.max_attempts:
        try:
            user_input = input(full_prompt).strip()

            # Handle empty input
            if not user_input:
                logger.debug(f"Empty input, using default: {config.default}")
                return config.valid_options[config.default]

            # Process input based on case sensitivity
            if not config.case_sensitive:
                user_input = user_input.lower()
                processed_options = {
                    k.lower(): v for k, v in config.valid_options.items()
                }
            else:
                processed_options = config.valid_options

            # Validate input
            if user_input in processed_options:
                logger.debug(f"Valid input received: {user_input}")
                return processed_options[user_input]

            # Handle invalid input
            attempts += 1
            remaining_attempts = config.max_attempts - attempts
            error_msg = (
                    config.error_message or
                    f"Invalid choice. Please enter one of: {', '.join(config.valid_options.keys())}"
            )

            if remaining_attempts > 0:
                print(f"{error_msg} ({remaining_attempts} attempts remaining)")
            else:
                print(f"{error_msg} (no attempts remaining)")

        except (KeyboardInterrupt, EOFError):
            logger.info("User interrupted input prompt")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during input: {str(e)}")
            return None

    logger.warning(f"Max attempts ({config.max_attempts}) exceeded")
    return None


def get_typed_input(
        prompt: str,
        input_type: type,
        default: Optional[Any] = None,
        validator: Optional[callable] = None
) -> Optional[Any]:
    """
    Get typed input from user with optional validation.

    Args:
        prompt: The prompt text to display
        input_type: The expected type of the input (int, float, str, etc.)
        default: Default value if user enters empty input
        validator: Optional function to validate the converted input

    Returns:
        Optional[Any]: The converted and validated input, or None if invalid/interrupted
    """
    try:
        user_input = input(f"{prompt} [default: {default}]: ").strip()

        if not user_input and default is not None:
            return default

        converted_input = input_type(user_input)

        if validator and not validator(converted_input):
            print("Input validation failed")
            return None

        return converted_input

    except ValueError:
        print(f"Invalid input. Expected type: {input_type.__name__}")
        return None
    except (KeyboardInterrupt, EOFError):
        logger.info("User interrupted input prompt")
        return None
