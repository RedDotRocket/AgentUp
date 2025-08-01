"""
Publisher Trust Management System.

This module provides comprehensive management of trusted publishers including
reputation tracking, revocation, and trust policy enforcement.
"""

import json
import time
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class PublisherTrustManager:
    """
    Manages publisher trust relationships, reputation, and revocation.

    This system tracks publisher behavior, manages trust levels, and handles
    publisher revocation and key rotation scenarios.
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.trust_config = config.get("publisher_trust", {})

        # Trust data storage
        self.publishers: dict[str, dict[str, Any]] = {}
        self.revoked_publishers: dict[str, dict[str, Any]] = {}
        self.publisher_history: dict[str, list[dict[str, Any]]] = {}

        # Trust policies
        self.trust_policies = self._load_trust_policies()

        # Reputation tracking
        self.reputation_scores: dict[str, float] = {}
        self.reputation_events: dict[str, list[dict[str, Any]]] = {}

        # Load persistent data
        self._load_trust_data()

        logger.info(f"Publisher trust manager initialized with {len(self.publishers)} publishers")

    def _load_trust_policies(self) -> dict[str, Any]:
        """Load trust policies from configuration"""
        default_policies = {
            "min_reputation_score": 0.5,
            "reputation_decay_days": 30,
            "auto_revoke_threshold": 0.2,
            "quarantine_new_publishers": True,
            "require_multiple_repositories": False,
            "max_trust_level_without_verification": "community"
        }

        configured_policies = self.trust_config.get("policies", {})
        default_policies.update(configured_policies)

        return default_policies

    def _load_trust_data(self):
        """Load persistent trust data from storage"""
        try:
            trust_data_path = Path(self.trust_config.get("data_path", "~/.agentup/trust_data.json")).expanduser()

            if trust_data_path.exists():
                with open(trust_data_path) as f:
                    data = json.load(f)

                self.publishers = data.get("publishers", {})
                self.revoked_publishers = data.get("revoked_publishers", {})
                self.publisher_history = data.get("publisher_history", {})
                self.reputation_scores = data.get("reputation_scores", {})
                self.reputation_events = data.get("reputation_events", {})

                logger.info(f"Loaded trust data: {len(self.publishers)} publishers, {len(self.revoked_publishers)} revoked")

        except Exception as e:
            logger.warning(f"Could not load trust data: {e}")

    def _save_trust_data(self):
        """Save trust data to persistent storage"""
        try:
            trust_data_path = Path(self.trust_config.get("data_path", "~/.agentup/trust_data.json")).expanduser()
            trust_data_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "publishers": self.publishers,
                "revoked_publishers": self.revoked_publishers,
                "publisher_history": self.publisher_history,
                "reputation_scores": self.reputation_scores,
                "reputation_events": self.reputation_events,
                "last_updated": time.time()
            }

            with open(trust_data_path, 'w') as f:
                json.dump(data, f, indent=2)

            logger.debug("Saved trust data to persistent storage")

        except Exception as e:
            logger.error(f"Could not save trust data: {e}")

    # === Publisher Management ===

    def register_publisher(
        self,
        publisher_id: str,
        repositories: list[str],
        trust_level: str = "community",
        description: str = "",
        metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Register a new trusted publisher"""

        # Check if publisher is revoked
        if publisher_id in self.revoked_publishers:
            return {
                "success": False,
                "error": f"Publisher '{publisher_id}' is revoked",
                "revocation_reason": self.revoked_publishers[publisher_id].get("reason")
            }

        # Validate trust level
        valid_trust_levels = {"community", "official"}
        if trust_level not in valid_trust_levels:
            return {
                "success": False,
                "error": f"Invalid trust level. Must be one of: {valid_trust_levels}"
            }

        # Create publisher record
        publisher_record = {
            "publisher_id": publisher_id,
            "repositories": repositories,
            "trust_level": trust_level,
            "description": description,
            "metadata": metadata or {},
            "registered_at": time.time(),
            "last_updated": time.time(),
            "status": "active",
            "verification_count": 0,
            "last_verification": None
        }

        # Apply quarantine policy for new publishers
        if self.trust_policies["quarantine_new_publishers"] and trust_level == "community":
            publisher_record["status"] = "quarantine"
            publisher_record["quarantine_until"] = time.time() + (7 * 24 * 3600)  # 7 days

        # Store publisher
        self.publishers[publisher_id] = publisher_record

        # Initialize reputation
        initial_reputation = 0.7 if trust_level == "official" else 0.5
        self.reputation_scores[publisher_id] = initial_reputation
        self.reputation_events[publisher_id] = []

        # Record history
        self._record_publisher_event(publisher_id, "registered", {
            "trust_level": trust_level,
            "repositories": len(repositories)
        })

        # Save to persistent storage
        self._save_trust_data()

        logger.info(f"Registered publisher '{publisher_id}' with trust level '{trust_level}'")

        return {
            "success": True,
            "publisher_id": publisher_id,
            "trust_level": trust_level,
            "status": publisher_record["status"],
            "reputation_score": initial_reputation
        }

    def update_publisher(
        self,
        publisher_id: str,
        repositories: list[str] | None = None,
        trust_level: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Update publisher information"""

        if publisher_id not in self.publishers:
            return {
                "success": False,
                "error": f"Publisher '{publisher_id}' not found"
            }

        publisher = self.publishers[publisher_id]
        changes = {}

        if repositories is not None:
            old_repos = set(publisher["repositories"])
            new_repos = set(repositories)

            if old_repos != new_repos:
                changes["repositories"] = {
                    "added": list(new_repos - old_repos),
                    "removed": list(old_repos - new_repos)
                }
                publisher["repositories"] = repositories

        if trust_level is not None and trust_level != publisher["trust_level"]:
            changes["trust_level"] = {
                "from": publisher["trust_level"],
                "to": trust_level
            }
            publisher["trust_level"] = trust_level

        if description is not None:
            changes["description"] = description
            publisher["description"] = description

        if metadata is not None:
            publisher["metadata"].update(metadata)
            changes["metadata"] = metadata

        if changes:
            publisher["last_updated"] = time.time()

            # Record history
            self._record_publisher_event(publisher_id, "updated", changes)

            # Save changes
            self._save_trust_data()

            logger.info(f"Updated publisher '{publisher_id}': {list(changes.keys())}")

        return {
            "success": True,
            "publisher_id": publisher_id,
            "changes": changes
        }

    def revoke_publisher(
        self,
        publisher_id: str,
        reason: str,
        revoked_by: str | None = None,
        effective_immediately: bool = True
    ) -> dict[str, Any]:
        """Revoke trust for a publisher"""

        if publisher_id not in self.publishers:
            return {
                "success": False,
                "error": f"Publisher '{publisher_id}' not found"
            }

        publisher = self.publishers[publisher_id]

        # Create revocation record
        revocation = {
            "publisher_id": publisher_id,
            "reason": reason,
            "revoked_by": revoked_by,
            "revoked_at": time.time(),
            "effective_immediately": effective_immediately,
            "original_record": publisher.copy()
        }

        # Move to revoked publishers
        self.revoked_publishers[publisher_id] = revocation
        del self.publishers[publisher_id]

        # Set reputation to zero
        self.reputation_scores[publisher_id] = 0.0

        # Record event
        self._record_publisher_event(publisher_id, "revoked", {
            "reason": reason,
            "revoked_by": revoked_by
        })

        # Save changes
        self._save_trust_data()

        logger.critical(f"Revoked publisher '{publisher_id}': {reason}")

        return {
            "success": True,
            "publisher_id": publisher_id,
            "revocation_reason": reason,
            "effective_immediately": effective_immediately
        }

    def restore_publisher(
        self,
        publisher_id: str,
        restored_by: str | None = None,
        new_trust_level: str = "community"
    ) -> dict[str, Any]:
        """Restore a revoked publisher"""

        if publisher_id not in self.revoked_publishers:
            return {
                "success": False,
                "error": f"Publisher '{publisher_id}' is not revoked"
            }

        revocation = self.revoked_publishers[publisher_id]
        original_record = revocation["original_record"]

        # Restore publisher with potentially downgraded trust level
        restored_record = original_record.copy()
        restored_record.update({
            "trust_level": new_trust_level,
            "status": "active",
            "last_updated": time.time(),
            "restored_at": time.time(),
            "restored_by": restored_by
        })

        # Move back to active publishers
        self.publishers[publisher_id] = restored_record
        del self.revoked_publishers[publisher_id]

        # Restore reputation with penalty
        original_reputation = self.reputation_scores.get(publisher_id, 0.5)
        restored_reputation = max(0.3, original_reputation * 0.7)  # 30% penalty
        self.reputation_scores[publisher_id] = restored_reputation

        # Record event
        self._record_publisher_event(publisher_id, "restored", {
            "restored_by": restored_by,
            "new_trust_level": new_trust_level,
            "reputation_penalty": original_reputation - restored_reputation
        })

        # Save changes
        self._save_trust_data()

        logger.info(f"Restored publisher '{publisher_id}' with trust level '{new_trust_level}'")

        return {
            "success": True,
            "publisher_id": publisher_id,
            "new_trust_level": new_trust_level,
            "reputation_score": restored_reputation
        }

    # === Reputation Management ===

    def update_reputation(
        self,
        publisher_id: str,
        event_type: str,
        impact: float,
        details: dict[str, Any] | None = None
    ):
        """Update publisher reputation based on events"""

        if publisher_id not in self.publishers and publisher_id not in self.revoked_publishers:
            logger.warning(f"Cannot update reputation for unknown publisher: {publisher_id}")
            return

        current_score = self.reputation_scores.get(publisher_id, 0.5)

        # Calculate new score with bounds checking
        new_score = max(0.0, min(1.0, current_score + impact))
        self.reputation_scores[publisher_id] = new_score

        # Record reputation event
        event = {
            "event_type": event_type,
            "impact": impact,
            "old_score": current_score,
            "new_score": new_score,
            "details": details or {},
            "timestamp": time.time()
        }

        if publisher_id not in self.reputation_events:
            self.reputation_events[publisher_id] = []

        self.reputation_events[publisher_id].append(event)

        # Check for auto-revocation
        if (new_score < self.trust_policies["auto_revoke_threshold"] and
            publisher_id in self.publishers):

            logger.warning(f"Publisher '{publisher_id}' reputation below threshold: {new_score}")

            # Auto-revoke if policy allows
            self.revoke_publisher(
                publisher_id,
                f"Automatic revocation due to low reputation score: {new_score}",
                revoked_by="system"
            )

        # Save changes
        self._save_trust_data()

        logger.debug(f"Updated reputation for '{publisher_id}': {current_score:.3f} -> {new_score:.3f} ({event_type})")

    def calculate_reputation_score(self, publisher_id: str) -> float:
        """Calculate current reputation score with time decay"""

        if publisher_id not in self.reputation_events:
            return self.reputation_scores.get(publisher_id, 0.5)

        # Apply time decay to reputation
        current_time = time.time()
        decay_days = self.trust_policies["reputation_decay_days"]
        decay_seconds = decay_days * 24 * 3600

        base_score = 0.5  # Neutral starting point
        weighted_score = 0.0
        total_weight = 0.0

        for event in self.reputation_events[publisher_id]:
            # Calculate time-based weight (more recent = higher weight)
            age = current_time - event["timestamp"]
            weight = max(0.1, 1.0 - (age / decay_seconds))

            weighted_score += event["impact"] * weight
            total_weight += weight

        if total_weight > 0:
            final_score = base_score + (weighted_score / total_weight)
        else:
            final_score = base_score

        # Bounds checking
        final_score = max(0.0, min(1.0, final_score))

        # Update stored score
        self.reputation_scores[publisher_id] = final_score

        return final_score

    def get_reputation_summary(self, publisher_id: str) -> dict[str, Any]:
        """Get detailed reputation summary for a publisher"""

        if publisher_id not in self.reputation_events:
            return {
                "publisher_id": publisher_id,
                "current_score": self.reputation_scores.get(publisher_id, 0.5),
                "event_count": 0,
                "recent_events": []
            }

        events = self.reputation_events[publisher_id]
        current_time = time.time()

        # Get recent events (last 30 days)
        recent_events = [
            event for event in events
            if current_time - event["timestamp"] < (30 * 24 * 3600)
        ]

        # Calculate trend
        if len(events) >= 2:
            old_score = events[-2]["new_score"]
            current_score = events[-1]["new_score"]
            trend = "improving" if current_score > old_score else "declining" if current_score < old_score else "stable"
        else:
            trend = "stable"

        return {
            "publisher_id": publisher_id,
            "current_score": self.calculate_reputation_score(publisher_id),
            "trend": trend,
            "event_count": len(events),
            "recent_events": len(recent_events),
            "last_updated": events[-1]["timestamp"] if events else None,
            "events": recent_events[-5:]  # Last 5 events
        }

    # === Trust Policy Enforcement ===

    def evaluate_publisher_trust(self, publisher_id: str) -> dict[str, Any]:
        """Evaluate overall trust for a publisher"""

        evaluation = {
            "publisher_id": publisher_id,
            "trusted": False,
            "trust_level": "unknown",
            "reputation_score": 0.0,
            "status": "unknown",
            "issues": [],
            "recommendations": []
        }

        # Check if publisher exists
        if publisher_id in self.revoked_publishers:
            evaluation.update({
                "trusted": False,
                "status": "revoked",
                "issues": [f"Publisher is revoked: {self.revoked_publishers[publisher_id]['reason']}"]
            })
            return evaluation

        if publisher_id not in self.publishers:
            evaluation["issues"].append("Publisher not found in trust registry")
            return evaluation

        publisher = self.publishers[publisher_id]
        reputation = self.calculate_reputation_score(publisher_id)

        evaluation.update({
            "trust_level": publisher["trust_level"],
            "reputation_score": reputation,
            "status": publisher["status"]
        })

        # Check reputation threshold
        min_reputation = self.trust_policies["min_reputation_score"]
        if reputation < min_reputation:
            evaluation["issues"].append(f"Reputation score {reputation:.3f} below minimum {min_reputation}")

        # Check quarantine status
        if publisher["status"] == "quarantine":
            quarantine_until = publisher.get("quarantine_until", 0)
            if time.time() < quarantine_until:
                evaluation["issues"].append("Publisher is in quarantine period")
                remaining_days = (quarantine_until - time.time()) / (24 * 3600)
                evaluation["recommendations"].append(f"Quarantine ends in {remaining_days:.1f} days")

        # Check repository requirements
        if (self.trust_policies["require_multiple_repositories"] and
            len(publisher["repositories"]) < 2):
            evaluation["issues"].append("Policy requires multiple repositories")

        # Overall trust determination
        evaluation["trusted"] = (
            len(evaluation["issues"]) == 0 and
            reputation >= min_reputation and
            publisher["status"] == "active"
        )

        return evaluation

    def get_trust_policies(self) -> dict[str, Any]:
        """Get current trust policies"""
        return self.trust_policies.copy()

    def update_trust_policy(self, policy_name: str, value: Any) -> bool:
        """Update a trust policy"""
        if policy_name in self.trust_policies:
            old_value = self.trust_policies[policy_name]
            self.trust_policies[policy_name] = value

            logger.info(f"Updated trust policy '{policy_name}': {old_value} -> {value}")

            # Re-evaluate all publishers if policy changed
            self._reevaluate_all_publishers()

            return True

        return False

    def _reevaluate_all_publishers(self):
        """Re-evaluate all publishers against current policies"""
        logger.info("Re-evaluating all publishers against updated policies")

        for publisher_id in list(self.publishers.keys()):
            evaluation = self.evaluate_publisher_trust(publisher_id)

            # Take action if publisher no longer meets trust requirements
            if not evaluation["trusted"] and "reputation" in evaluation["issues"][0]:
                self.update_reputation(
                    publisher_id,
                    "policy_reevaluation",
                    -0.1,  # Small penalty for not meeting updated policies
                    {"policy_issues": evaluation["issues"]}
                )

    # === History and Events ===

    def _record_publisher_event(self, publisher_id: str, event_type: str, details: dict[str, Any]):
        """Record a publisher event in history"""
        if publisher_id not in self.publisher_history:
            self.publisher_history[publisher_id] = []

        event = {
            "event_type": event_type,
            "timestamp": time.time(),
            "details": details
        }

        self.publisher_history[publisher_id].append(event)

        # Keep only last 100 events per publisher
        if len(self.publisher_history[publisher_id]) > 100:
            self.publisher_history[publisher_id] = self.publisher_history[publisher_id][-100:]

    def get_publisher_history(self, publisher_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Get event history for a publisher"""
        history = self.publisher_history.get(publisher_id, [])
        return history[-limit:]

    # === Querying and Statistics ===

    def list_publishers(
        self,
        trust_level: str | None = None,
        status: str | None = None,
        min_reputation: float | None = None
    ) -> list[dict[str, Any]]:
        """List publishers with optional filtering"""

        publishers = []

        for publisher_id, publisher in self.publishers.items():
            # Apply filters
            if trust_level and publisher["trust_level"] != trust_level:
                continue

            if status and publisher["status"] != status:
                continue

            reputation = self.calculate_reputation_score(publisher_id)
            if min_reputation and reputation < min_reputation:
                continue

            # Build result
            result = publisher.copy()
            result["reputation_score"] = reputation
            result["is_trusted"] = self.evaluate_publisher_trust(publisher_id)["trusted"]

            publishers.append(result)

        # Sort by reputation descending
        publishers.sort(key=lambda x: x["reputation_score"], reverse=True)

        return publishers

    def get_trust_statistics(self) -> dict[str, Any]:
        """Get overall trust system statistics"""

        stats = {
            "total_publishers": len(self.publishers),
            "revoked_publishers": len(self.revoked_publishers),
            "trust_levels": {
                "official": 0,
                "community": 0
            },
            "status_counts": {
                "active": 0,
                "quarantine": 0
            },
            "reputation_distribution": {
                "high": 0,     # >= 0.8
                "medium": 0,   # 0.5 - 0.8
                "low": 0       # < 0.5
            },
            "avg_reputation": 0.0,
            "trusted_publishers": 0
        }

        total_reputation = 0.0

        for publisher_id, publisher in self.publishers.items():
            # Trust level counts
            trust_level = publisher["trust_level"]
            if trust_level in stats["trust_levels"]:
                stats["trust_levels"][trust_level] += 1

            # Status counts
            status = publisher["status"]
            if status in stats["status_counts"]:
                stats["status_counts"][status] += 1

            # Reputation distribution
            reputation = self.calculate_reputation_score(publisher_id)
            total_reputation += reputation

            if reputation >= 0.8:
                stats["reputation_distribution"]["high"] += 1
            elif reputation >= 0.5:
                stats["reputation_distribution"]["medium"] += 1
            else:
                stats["reputation_distribution"]["low"] += 1

            # Trusted count
            if self.evaluate_publisher_trust(publisher_id)["trusted"]:
                stats["trusted_publishers"] += 1

        # Calculate average reputation
        if stats["total_publishers"] > 0:
            stats["avg_reputation"] = total_reputation / stats["total_publishers"]

        return stats
