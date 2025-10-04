# Redis Caching Setup

Streetrace supports Redis caching for LLM responses to improve performance and reduce costs during local development. This guide shows how to set up and use Redis caching.

## Prerequisites

- Docker installed on your system
- Streetrace installed with dependencies

## Quick Start

### 1. Start Redis Server

Pull and run the Redis Stack container with both Redis server and Redis Insight:

```bash
docker pull redis/redis-stack
docker run -d --name streetrace-redis -p 6380:6379 -p 8001:8001 redis/redis-stack
```

**Note**: We use port `6380` for Redis to avoid conflicts with any existing Redis instance on the default `6379` port.

### 2. Configure Environment Variables

Create a `.env` file in your project root or set environment variables:

```bash
# .env file
REDIS_HOST=localhost
REDIS_PORT=6380
REDIS_PASSWORD=  # Optional, leave empty if no password
REDIS_TTL_SECONDS=3600  # Optional, cache expiry in seconds (1 hour default)
```

Available environment variables:
- `REDIS_HOST`: Redis server hostname (default: `localhost`)
- `REDIS_PORT`: Redis server port (default: `6379`, use `6380` for the Docker setup above)
- `REDIS_PASSWORD`: Redis password if authentication is required (optional)
- `REDIS_TTL_SECONDS`: Cache time-to-live in seconds (optional, uses LiteLLM default if not set)

### 3. Enable Caching

Run Streetrace with the `--cache` flag to enable Redis caching:

```bash
poetry run streetrace --model=your-model --cache
```

## Monitoring Cache Usage

### Using Redis Insight

Redis Insight provides a web-based GUI to monitor your Redis cache:

1. Open your browser and go to `http://localhost:8001`
2. Connect to your Redis instance (it should auto-detect the local Redis server)
3. Browse cached keys to see LLM response caches
4. Monitor cache hit/miss statistics

### Using Redis CLI

If you prefer command-line tools, you can connect to Redis directly:

```bash
# Connect to Redis CLI (inside the container)
docker exec -it streetrace-redis redis-cli

# View all cached keys
KEYS *

# Get cache statistics
INFO stats

# Monitor real-time commands
MONITOR
```

## Cache Behavior

- **Cache Key**: LiteLLM generates cache keys based on the model, messages, and parameters
- **Expiry**: Cached responses expire based on `REDIS_TTL_SECONDS` (default handled by LiteLLM)
- **Cache Hits**: Identical requests return cached responses immediately
- **Performance**: Significant speedup for repeated queries during development

## Troubleshooting

### Redis Connection Issues

If you see connection errors:

1. **Check if Redis is running**:
   ```bash
   docker ps | grep streetrace-redis
   ```

2. **Check port availability**:
   ```bash
   netstat -an | grep 6380
   ```

3. **Verify environment variables**:
   ```bash
   echo $REDIS_HOST $REDIS_PORT
   ```

### Missing Redis Package

If you get an import error about the Redis package:

```bash
# Redis should be installed as a dev dependency
poetry install

# Or install manually
pip install redis
```

### Cache Not Working

1. **Verify caching is enabled**: Check that you're using the `--cache` flag
2. **Check logs**: Streetrace logs when Redis caching is enabled/disabled
3. **Monitor Redis**: Use Redis Insight or CLI to verify keys are being created

## Production Considerations

**Important**: This caching setup is intended for local development only. For production use:

- Use a proper Redis deployment with persistence
- Configure appropriate security (authentication, network isolation)
- Set appropriate TTL values based on your use case
- Monitor cache memory usage and eviction policies

## Stopping Redis

To stop and remove the Redis container:

```bash
docker stop streetrace-redis
docker rm streetrace-redis
```

## Advanced Configuration

For advanced Redis configurations, you can:

1. **Use Redis configuration file**: Mount a custom `redis.conf`
2. **Enable persistence**: Configure RDB or AOF persistence
3. **Set memory limits**: Configure `maxmemory` and eviction policies
4. **Use Redis Cluster**: For distributed caching scenarios

Example with custom configuration:

```bash
docker run -d --name streetrace-redis \
  -p 6380:6379 -p 8001:8001 \
  -v /path/to/redis.conf:/redis-stack.conf \
  redis/redis-stack redis-stack-server /redis-stack.conf
```