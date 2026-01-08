import uvicorn
import asyncio
import sys

def main():
    """
    Dedicated startup script to ensure WindowsProactorEventLoopPolicy is applied correctly.
    This resolves the 'NotImplementedError' with Playwright on Windows.
    Reload is disabled to prevent subprocess loop policy reset.
    """
    print("Iniciando servidor con politica de EventLoop especifica para Windows...")
    
    if sys.platform == 'win32':
        # Force Proactor for Playwright
        try:
            policy = asyncio.WindowsProactorEventLoopPolicy()
            asyncio.set_event_loop_policy(policy)
            print(f"Politica establecida: {type(policy).__name__}")
        except Exception as e:
            print(f"Error al establecer politica: {e}")

    # Run without reload to ensure executing in this same process/loop context
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    main()
