"""
Network Optimizer for Cloud Platforms
Advanced network stability and session persistence
"""

import asyncio
import logging
import random
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class NetworkMetrics:
    """Network performance metrics"""
    latency: float
    success_rate: float
    error_count: int
    last_check: float

class NetworkOptimizer:
    """Advanced network optimization for cloud platforms"""
    
    def __init__(self):
        self.metrics: Dict[str, NetworkMetrics] = {}
        self.connection_pool = {}
        self.adaptive_delays = {}
        
    async def optimize_connection(self, client, operation: str) -> bool:
        """Optimize connection for specific operation"""
        try:
            # Pre-connection optimization
            await self._pre_optimize(operation)
            
            # Adaptive delay based on recent performance
            delay = self._calculate_adaptive_delay(operation)
            if delay > 0:
                await asyncio.sleep(delay)
            
            # Connection health check
            if not await self._health_check(client):
                await self._connection_recovery(client)
            
            return True
            
        except Exception as e:
            logger.error(f"Connection optimization failed: {e}")
            return False
    
    async def _pre_optimize(self, operation: str):
        """Pre-operation optimization"""
        # Network-specific optimizations
        optimizations = {
            'message': self._optimize_messaging,
            'join': self._optimize_joining,
            'bulk': self._optimize_bulk_operations
        }
        
        if operation in optimizations:
            await optimizations[operation]()
    
    async def _optimize_messaging(self):
        """Optimize for messaging operations"""
        # Reduce message frequency during high IP change periods
        await asyncio.sleep(random.uniform(0.5, 2.0))
    
    async def _optimize_joining(self):
        """Optimize for channel joining"""
        # Longer delays for join operations
        await asyncio.sleep(random.uniform(2.0, 5.0))
    
    async def _optimize_bulk_operations(self):
        """Optimize for bulk operations"""
        # Significant delays for bulk operations
        await asyncio.sleep(random.uniform(5.0, 10.0))
    
    def _calculate_adaptive_delay(self, operation: str) -> float:
        """Calculate adaptive delay based on recent performance"""
        if operation not in self.adaptive_delays:
            self.adaptive_delays[operation] = 1.0
        
        # Increase delay if recent errors
        current_delay = self.adaptive_delays[operation]
        
        # Gradually reduce delay over time (exponential decay)
        self.adaptive_delays[operation] = max(0.1, current_delay * 0.95)
        
        return current_delay
    
    async def _health_check(self, client) -> bool:
        """Quick connection health check"""
        try:
            start_time = time.time()
            await client.get_me()
            latency = time.time() - start_time
            
            # Update metrics
            self._update_metrics('health_check', latency, True)
            
            return latency < 10.0  # Consider healthy if < 10s
            
        except Exception as e:
            self._update_metrics('health_check', 0, False)
            logger.warning(f"Health check failed: {e}")
            return False
    
    async def _connection_recovery(self, client):
        """Attempt connection recovery"""
        logger.info("Attempting connection recovery...")
        
        # Progressive recovery delays
        for attempt in range(3):
            try:
                delay = 2 ** attempt  # Exponential backoff
                await asyncio.sleep(delay)
                
                # Simple recovery operation
                await client.get_me()
                logger.info(f"Connection recovered on attempt {attempt + 1}")
                return
                
            except Exception as e:
                logger.warning(f"Recovery attempt {attempt + 1} failed: {e}")
        
        logger.error("Connection recovery failed after 3 attempts")
    
    def _update_metrics(self, operation: str, latency: float, success: bool):
        """Update performance metrics"""
        if operation not in self.metrics:
            self.metrics[operation] = NetworkMetrics(0, 1.0, 0, time.time())
        
        metric = self.metrics[operation]
        
        # Update latency (moving average)
        metric.latency = (metric.latency * 0.8) + (latency * 0.2)
        
        # Update success rate
        if success:
            metric.success_rate = min(1.0, metric.success_rate + 0.1)
        else:
            metric.success_rate = max(0.0, metric.success_rate - 0.2)
            metric.error_count += 1
            
            # Increase adaptive delay on errors
            if operation in self.adaptive_delays:
                self.adaptive_delays[operation] = min(30.0, self.adaptive_delays[operation] * 1.5)
        
        metric.last_check = time.time()
    
    def get_network_status(self) -> Dict:
        """Get current network status"""
        return {
            'metrics': {op: {
                'latency': m.latency,
                'success_rate': m.success_rate,
                'error_count': m.error_count
            } for op, m in self.metrics.items()},
            'adaptive_delays': self.adaptive_delays,
            'overall_health': self._calculate_overall_health()
        }
    
    def _calculate_overall_health(self) -> str:
        """Calculate overall network health"""
        if not self.metrics:
            return 'unknown'
        
        avg_success = sum(m.success_rate for m in self.metrics.values()) / len(self.metrics)
        
        if avg_success > 0.9:
            return 'excellent'
        elif avg_success > 0.7:
            return 'good'
        elif avg_success > 0.5:
            return 'fair'
        else:
            return 'poor'

# Global optimizer instance
network_optimizer = NetworkOptimizer()