async def search_yts_multiple(query: str, limit: int = 5):
    """
    Search YouTube videos using abhi-api
    :param query: Search term
    :param limit: Maximum number of video results to display (default 5)
    :return: Formatted response string with compact box design
    """
    url = f"https://abhi-api.vercel.app/api/search/yts?text={query.replace(' ', '+')}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") and data.get("result"):
            results = data["result"]
            if not isinstance(results, list):
                results = [results]
                
            # Compact box design using simpler Unicode characters
            output_message = f"┌─ YouTube Search: '{query}' ─┐\n"
            
            for i, res in enumerate(results[:limit], 1):
                output_message += f"Video {i}: {res.get('title', 'N/A')}\n"
                output_message += f"Link: {res.get('url', 'N/A')}\n"
                output_message += "\n"
            
            # Get creator and log for debugging
            creator = data.get('creator', 'Unknown')
            logger.info(f"Raw creator value: {creator}")
            # Replace the exact string or its variations
            if creator == "𝙰𝙱𝙷𝙸𝚂𝙷𝙴𝙺 𝚂𝚄𝚁𝙴𝚂𝙷🍀" or "ABHISHEK SURESH" in creator:
                creator = "@Farukvaiyq01"
            output_message += f"└─ Powered by: {creator} ─┘"
            return output_message
        else:
            return "Sorry, I couldn’t find any results for your search. Try a different query!"
    except requests.exceptions.RequestException as e:
        logger.error(f"Error searching YouTube: {e}")
        return "Something went wrong with the search. Please try again with a different term!"