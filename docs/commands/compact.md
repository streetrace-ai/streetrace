# `/compact` Command

## Description
The `/compact` command summarizes your conversation history with StreetRace to reduce token count while maintaining context and important information.

## Usage
```
/compact
```

## How It Works
When you invoke the `/compact` command:

1. StreetRace creates a special prompt asking the AI model to summarize the conversation
2. The AI model generates a concise summary that preserves key information, including:
   - Important points and decisions
   - File paths and code changes
   - Critical context needed for conversation continuity
3. The original conversation history is replaced with a single message containing this summary
4. You can continue the conversation where you left off, but with significantly fewer tokens used

## Benefits
- **Reduce Token Usage**: For long conversations, compacting can significantly reduce the token count
- **Avoid Context Limitations**: Prevents hitting token limits of the underlying AI model
- **Maintain Continuity**: Unlike starting a new conversation, the AI retains context of previous discussions
- **Improve Response Quality**: By removing noise and focusing on essential information

## When to Use
Consider using the `/compact` command when:
- The conversation has become lengthy and might be approaching token limits
- You want to continue the conversation but reduce costs
- You've completed one task and are moving to a different but related topic
- Responses from the AI seem to be losing coherence due to context overflow

## Example
```
User: Let's analyze the performance of this sorting algorithm.
AI: [Provides detailed analysis of the sorting algorithm]
User: Now let's optimize it for better space complexity.
AI: [Suggests optimizations with code examples]
User: /compact
AI: History compacted successfully.
User: What other sorting algorithms might work better for this case?
AI: [Provides recommendations based on previous discussion, but using much fewer tokens]
```

## Notes
- You cannot undo a compact operation, so use it when you're confident you want to summarize
- The quality of the summary depends on the AI model - more advanced models will usually produce better summaries
- Even after compacting, you can still view the summarized history using the `/history` command