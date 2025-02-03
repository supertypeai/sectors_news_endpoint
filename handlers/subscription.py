import json
from flask import Blueprint, request, jsonify
from middleware.api_key import require_api_key
from database import supabase

subscription_module = Blueprint('subscription', __name__)

@subscription_module.route("/subscribe", methods=["POST"])
@require_api_key
def subscribe():
    """
    @API-function
    @brief Register a user to subscribe to a topic.
    
    @request-args
    user: str
    topic: str
    
    @return JSON response indicating success or failure.
    """
    input_data = request.get_json()
    user = input_data.get("user").upper()
    topic = input_data.get("topic").upper()

    if not user or not topic:
        return jsonify({"status": "error", "message": "User and topic are required"}), 400

    # Check if the user already exists in the subscriptions table
    response = supabase.table("news_subscriptions").select("*").eq("user", user).execute()

    if response.data:
        # User exists, update the topic array
        existing_topics = response.data[0]["topic"]
        if topic not in existing_topics:
            existing_topics.append(topic)
            update_response = supabase.table("news_subscriptions").update({"topic": existing_topics}).eq("user", user).execute()
            if len(update_response.data) > 0:
                return jsonify({"status": "success", "message": "Subscribed successfully"}), 200
            else:
                return jsonify({"status": "error", "message": "Update failed"}), 400
        else:
            return jsonify({"status": "success", "message": "Already subscribed to this topic"}), 200
    else:
        # User does not exist, insert a new record
        response = supabase.table("news_subscriptions").insert({"user": user, "topic": [topic]}).execute()
        if len(response.data) > 0:
            return jsonify({"status": "success", "message": "Subscribed successfully"}), 201
        else:
            return jsonify({"status": "error", "message": "Insert failed"}), 400


@subscription_module.route("/unsubscribe", methods=["POST"])
@require_api_key
def unsubscribe():
    """
    @API-function
    @brief Unregister a user from a topic.
    
    @request-args
    user: str
    topic: str
    
    @return JSON response indicating success or failure.
    """
    input_data = request.get_json()
    user = input_data.get("user").upper()
    topic = input_data.get("topic").upper()

    if not user or not topic:
        return jsonify({"status": "error", "message": "User and topic are required"}), 400

    # Check if the user exists in the subscriptions table
    response = supabase.table("news_subscriptions").select("*").eq("user", user).execute()

    if response.data:
        # User exists, update the topic array
        existing_topics = response.data[0]["topic"]
        if topic in existing_topics:
            existing_topics.remove(topic)
            if existing_topics:
                update_response = supabase.table("news_subscriptions").update({"topic": existing_topics}).eq("user", user).execute()
                if len(update_response.data) > 0:
                    return jsonify({"status": "success", "message": "Unsubscribed successfully"}), 200
                else:
                    return jsonify({"status": "error", "message": "Update failed"}), 400
            else:
                delete_response = supabase.table("news_subscriptions").delete().eq("user", user).execute()
                if len(delete_response.data) > 0:
                    return jsonify({"status": "success", "message": "Unsubscribed successfully"}), 200
                else:
                    return jsonify({"status": "error", "message": "Delete failed"}), 400
        else:
            return jsonify({"status": "error", "message": "User is not subscribed to this topic"}), 400
    else:
        return jsonify({"status": "error", "message": "User not found"}), 400
