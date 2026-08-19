import hydra
from openteach.components import TeleOperator

@hydra.main(version_base = '1.2', config_path = 'configs', config_name = 'teleop')
def main(configs):
    teleop = TeleOperator(configs)
    processes = teleop.get_processes()

    try:
        for process in processes:
            process.start()

        for process in processes:
            process.join()
    except KeyboardInterrupt:
        print("Stopping Open Teach processes...")
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
        for process in processes:
            if process.pid is not None:
                process.join(timeout=5)

if __name__ == '__main__':
    main()
