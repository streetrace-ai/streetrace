# Changes Summary

## Separation of Concerns: SystemContext and PromptProcessor

Based on the SOLID principles, particularly the Single Responsibility Principle, we've separated two distinct responsibilities that were previously mixed in the `PromptProcessor` class:

1. **SystemContext** is now responsible for:
   - Loading the system message from `system.md` in the config directory
   - Loading and combining project context files from the config directory
   - Providing this context to HistoryManager for initializing conversation history

2. **PromptProcessor** is now focused on:
   - Processing user prompts (like parsing @mentions) 
   - Loading file contents from mentioned files
   - Building the prompt context with mentions

## Modified Files:

1. **src/streetrace/system_context.py** (New File):
   - Created a dedicated class for loading system and project context
   - Moved code from PromptProcessor related to system/project context
   - Maintains error handling and logging as per existing patterns

2. **src/streetrace/prompt_processor.py**:
   - Simplified to focus on prompt processing and file mentions
   - Removed system/project context handling responsibilities
   - Updated PromptContext dataclass to no longer include system_message and project_context

3. **src/streetrace/history_manager.py**:
   - Now accepts SystemContext as a dependency
   - Uses SystemContext to get system_message and project_context during history initialization
   - No longer uses PromptProcessor for system/project context

4. **src/streetrace/application.py**:
   - Added SystemContext to dependencies
   - Updated non-interactive mode to use SystemContext for system/project context
   - Now passes SystemContext to HistoryManager

5. **src/streetrace/main.py**:
   - Updated to create and initialize SystemContext
   - Modified initialization of PromptProcessor to no longer include config_dir
   - Passes SystemContext to HistoryManager and Application

6. **Tests**:
   - Created tests/test_system_context.py for the new SystemContext class
   - Updated tests/test_mentions.py to work with modified PromptProcessor
   - Updated tests/test_history_manager.py to use SystemContext
   - Updated tests/test_application.py to include SystemContext

## Benefits:

- **Better separation of concerns**: Each class now has a single, focused responsibility
- **Improved maintainability**: Changes to system context handling won't affect prompt processing and vice versa
- **Enhanced testability**: Each responsibility can be tested independently
- **Reduced coupling**: Components are more loosely coupled, with clearer dependencies
- **Future extensibility**: Each aspect can evolve independently as requirements change